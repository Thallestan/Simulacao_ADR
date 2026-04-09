import argparse
import socket
import threading
import time
import csv

# Variáveis globais de Estado (Fonte da Verdade)
buffer_atual = 0
qualidade_atual = "HIGH"       # Estado global da qualidade
ultimo_t_download = 0.0        # Memória do tempo do último bloco
lock = threading.Lock()
executando = True

def main():
    global buffer_atual, executando
    
    # =====================================================================
    # BLOCO 1: RECEBIMENTO DE PARÂMETROS DA TOPOLOGIA
    # Lê as ordens enviadas pelo arquivo 'topology.py'
    # =====================================================================
    parser = argparse.ArgumentParser(description="Smart Sampa: DASH Client")
    parser.add_argument('--server', type=str, required=True, help="IP do Servidor")
    parser.add_argument('--port', type=int, default=8080, help="Porta TCP")
    parser.add_argument('--duration', type=int, default=60, help="Duração do teste")
    parser.add_argument('--log', type=str, required=True, help="Caminho do arquivo CSV")
    args = parser.parse_args()

    # =====================================================================
    # BLOCO 2: CONFIGURAÇÃO DOS LIMITES FÍSICOS E HISTERESE
    # Definição das regras de negócio do algoritmo ABR e da Memória RAM
    # =====================================================================
    BUFFER_MAX = 20           # Limite Físico: Tamanho máximo da RAM alocada
    HIGH_WATERMARK = 15       # Gatilho de Pausa: Se bater aqui, para de baixar
    RESUME_WATERMARK = 5      # Gatilho de Retomada: Só volta a baixar quando cair pra cá
    SAFE_WATERMARK = 8        # Gatilho de Qualidade: Tem gordura suficiente pra pedir Alta Definição?
    PLAYBACK_INTERVAL = 1.0   # Consumo: O player gasta 1 chunk a cada 1 segundo

    # =====================================================================
    # BLOCO 3: INICIALIZAÇÃO DA TELEMETRIA (LOGS)
    # =====================================================================
    csv_file = open(args.log, 'w', newline='')
    writer = csv.writer(csv_file)
    writer.writerow(['Tempo_s', 'Evento', 'Qualidade', 'Tamanho_Buffer', 'Vazao_Mbps', 'Tempo_Download_s'])
    tempo_inicio = time.time()

    def gravar_log(evento, qualidade, buffer_sz, vazao="-", t_down="-"):
        tempo = round(time.time() - tempo_inicio, 3)
        with lock:
            writer.writerow([tempo, evento, qualidade, buffer_sz, vazao, t_down])
            csv_file.flush()

    # =====================================================================
    # BLOCO 4: THREAD DE CONSUMO (O PLAYER DE VÍDEO)
    # =====================================================================
    def thread_playback():
        global buffer_atual, executando, qualidade_atual, ultimo_t_download
        while executando:
            time.sleep(PLAYBACK_INTERVAL)
            with lock:
                if buffer_atual > 0: 
                    buffer_atual -= 1
                buf_copy = buffer_atual              
            gravar_log('Playback', qualidade_atual, buf_copy, "-", ultimo_t_download)

    # =====================================================================
    # BLOCO 5: THREAD DE REDE E ALGORITMO ABR
    # O "Cérebro" do cliente. Puxa os blocos via TCP e ajusta a qualidade.
    # =====================================================================
    def thread_rede():
        global buffer_atual, executando, qualidade_atual, ultimo_t_download
        estado_rede = "RUNNING"
        
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((args.server, args.port))
                
                # Loop principal que roda até o tempo acabar
                while executando and (time.time() - tempo_inicio) < args.duration:
                    with lock: ocupacao = buffer_atual
                    
                    # --- 5.1: CONTROLE DE FLUXO E HISTERESE ---
                    if ocupacao >= HIGH_WATERMARK:
                        estado_rede = "PAUSED"
                        gravar_log('Pausa (Buffer Full)', qualidade_atual, ocupacao)
                    
                    if estado_rede == "PAUSED":
                        if ocupacao <= RESUME_WATERMARK:
                            estado_rede = "RUNNING"
                            gravar_log('Retomada (Buffer Low)', qualidade_atual, ocupacao)
                        else:
                            time.sleep(0.5) # Aguarda o player esvaziar o buffer
                            continue

                    # --- 5.2: REQUISIÇÃO DO ARQUIVO (DOWNLOAD) ---
                    comando = b"GET_CHUNK_HIGH" if qualidade_atual == "HIGH" else b"GET_CHUNK_LOW"
                    t_start = time.time()
                    s.sendall(comando)
                    
                    
                    # Calcula o tamanho que precisa baixar e faz o download contínuo
                    tamanho = (1024*1024) if qualidade_atual == "HIGH" else (250*1024)
                    recebido = 8
                    while recebido < tamanho:
                        data = s.recv(16384)
                        if not data: break
                        recebido += len(data)
                    
                    # Calcula a banda efetiva gasta neste download
                    t_end = time.time()
                    vazao = round((tamanho * 8) / (1_000_000 * (t_end - t_start)), 2)
                    
                    # --- 5.3: PROTEÇÃO FÍSICA DE RAM (OVERFLOW) ---
                    with lock:
                        if buffer_atual < BUFFER_MAX:
                            buffer_atual += 1
                        else:
                            gravar_log('Overflow (RAM)', qualidade_atual, buffer_atual)
                        buf_copy = buffer_atual

                    # --- 5.4: TOMADA DE DECISÃO DE QUALIDADE (ABR) ---
                    t_download = round(time.time() - t_start, 3)
                    ultimo_t_download = t_download 
                    old_q = qualidade_atual
                    
                    # (BBA - Buffer-Based Algorithm):
                    # Só reduz a qualidade se a rede estiver lenta E o buffer estiver secando (< 5)
                    if t_download > PLAYBACK_INTERVAL and buf_copy < 5:
                        qualidade_atual = "LOW"
                        
                    # Regra: Download rápido E buffer seguro
                    elif t_download < 0.5 and buf_copy >= SAFE_WATERMARK:
                        qualidade_atual = "HIGH"
                    
                    if old_q != qualidade_atual:
                        evento = f"Mudança: {old_q}->{qualidade_atual}"
                        gravar_log(evento, qualidade_atual, buf_copy, vazao, t_download)
                    else:
                        gravar_log('Download Concluido', qualidade_atual, buf_copy, vazao, t_download)
                        
        except Exception: 
            executando = False

    # =====================================================================
    # BLOCO 6: ORQUESTRAÇÃO
    # Dispara as tarefas em paralelo e segura o programa rodando pelo tempo certo
    # =====================================================================
    t_play = threading.Thread(target=thread_playback, daemon=True)
    t_net = threading.Thread(target=thread_rede, daemon=True)
    
    t_play.start()
    t_net.start()
    
    while executando and (time.time() - tempo_inicio) < args.duration: 
        time.sleep(1)
        
    executando = False
    csv_file.close()

if __name__ == '__main__':
    main()