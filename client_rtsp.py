import argparse
import socket
import threading
import time
import csv

# Variáveis globais com mutex (lock) para controle de concorrência
buffer_atual = 0
lock = threading.Lock()
executando = True

def main():
    global buffer_atual, executando
    
    # =====================================================================
    # BLOCO 1: RECEBIMENTO DE PARÂMETROS DA TOPOLOGIA
    # Recebe instruções da topologia
    # =====================================================================
    parser = argparse.ArgumentParser(description="Smart Sampa: RTSP Client")
    parser.add_argument('--server', type=str, required=True, help="IP do Servidor")
    parser.add_argument('--port', type=int, default=8554, help="Porta TCP RTSP")
    parser.add_argument('--duration', type=int, default=60, help="Tempo do teste em seg")
    parser.add_argument('--log', type=str, required=True, help="Caminho do CSV")
    args = parser.parse_args()

    PORT_RTSP = args.port
    PORT_RTP = args.port + 1
    
    # =====================================================================
    # BLOCO 2: PARÂMETROS VITAIS DE CONTROLE DE BUFFER
    # Configurações de buffer
    # =====================================================================
    BUFFER_MAX = 2000         # Memória física total da aplicação
    HIGH_WATERMARK = 1500     # Pede PAUSE preventivo
    LOW_WATERMARK = 500      # Pede PLAY para retomar
    PLAYBACK_INTERVAL = 0.1 # Renderiza 1 pacote a cada 0.1s (10 FPS)
    
    # =====================================================================
    # BLOCO 3: TELEMETRIA E LOGS (GRAVAÇÃO CSV)
    # Geração de logs para análise
    # =====================================================================
    csv_file = open(args.log, 'w', newline='')
    writer = csv.writer(csv_file)
    writer.writerow(['Tempo_s', 'Evento', 'Tamanho_Buffer_Pacotes'])
    tempo_inicio = time.time()
    
    sock_controle = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    
    def gravar_log(evento, tranca=True):
        tempo = round(time.time() - tempo_inicio, 3)
        if tranca:
            with lock: 
                writer.writerow([tempo, evento, buffer_atual])
        else:
            writer.writerow([tempo, evento, buffer_atual])
        csv_file.flush()

    # =====================================================================
    # BLOCO 4: THREAD DE CONSUMO (O PLAYER DE VÍDEO)
    # Definição do consumo do player (cliente)
    # =====================================================================
    def thread_playback():
        global buffer_atual, executando
        while executando:
            time.sleep(0.1) # Taxa de atualização da tela
            with lock:
                # Consome 65 pacotinhos por ciclo
                buffer_atual = max(0, buffer_atual - 65)

    # =====================================================================
    # BLOCO 5: THREAD DE REDE (RTP/UDP + SINALIZAÇÃO TCP)
    # Recebe os pacotes do servidor e envia comandos de play e pause
    # =====================================================================
    def thread_rede_udp():
        global buffer_atual, executando
        
        # Estabelece a conexão de controle via TCP
        sock_controle.connect((args.server, PORT_RTSP))
        
        # Prepara o receptor de mídia via UDP
        sock_udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock_udp.bind(('0.0.0.0', PORT_RTP))
        sock_udp.settimeout(0.1) # Timeout curto para não prender o laço
        
        # Dispara o fluxo de vídeo (Push request)
        print("[*] Enviando PLAY inicial para o servidor RTSP...")
        sock_controle.sendall(b"PLAY\n")
        estado_atual = "PLAY"
        
        # Inicialize com -1 para sincronizar no primeiro pacote recebido
        seq_esperado = -1  
        
        while executando and (time.time() - tempo_inicio) < args.duration:
            try:
                dados, _ = sock_udp.recvfrom(65535) 
                
                # --- 5.1: DETECÇÃO DE PERDA DE PACOTES ---
                try:
                    partes = dados.split(b'|', 1)
                    if len(partes) >= 2:
                        seq_recebido = int(partes[0].decode('utf-8'))
                        
                        if seq_esperado == -1:
                            seq_esperado = seq_recebido
                        
                        if seq_recebido > seq_esperado:
                            perdas = seq_recebido - seq_esperado
                            gravar_log(f"Perda de Rede ({perdas} pkts)", tranca=False)
                        
                        seq_esperado = seq_recebido + 1
                except (ValueError, UnicodeDecodeError, IndexError):
                    pass 
                
                # --- 5.2: LIMITE FÍSICO DE RAM ---
                with lock:
                    if buffer_atual < BUFFER_MAX:
                        buffer_atual += 1
                    else:
                        gravar_log("Overflow", tranca=False)
            
            except socket.timeout:
                pass

            with lock:
                ocupacao = buffer_atual
            
            # --- 5.3: TRATAMENTO DE ESTOURO (CONTROLE DE BUFFER DA APLICAÇÃO) ---
            if ocupacao >= HIGH_WATERMARK and estado_atual == "PLAY":
                print(f"[!] GATILHO DE PROTEÇÃO: Buffer em {ocupacao}. Enviando PAUSE via TCP.")
                sock_controle.sendall(b"PAUSE\n")
                estado_atual = "PAUSE"
                gravar_log("Enviou RTSP PAUSE (Risco)", tranca=False)
                
            elif ocupacao <= LOW_WATERMARK and estado_atual == "PAUSE":
                print(f"[*] ZONA SEGURA: Buffer em {ocupacao}. Enviando PLAY via TCP.")
                sock_controle.sendall(b"PLAY\n")
                estado_atual = "PLAY"
                gravar_log("Enviou RTSP PLAY (Seguro)", tranca=False)

        executando = False
    
    # =====================================================================
    # BLOCO 6: ORQUESTRAÇÃO
    # Recebe instruções da topologia e executa
    # =====================================================================
    t_play = threading.Thread(target=thread_playback, daemon=True)
    t_rede = threading.Thread(target=thread_rede_udp, daemon=True)
    t_play.start()
    t_rede.start()
    
    # Controlador central de tempo gera telemetria secundária contínua
    while executando and (time.time() - tempo_inicio) < args.duration:
        time.sleep(1)
        gravar_log("Status Buffer Continuo")
        
    executando = False
    sock_controle.sendall(b"PAUSE\n") # Para o servidor graciosamente no fim
    sock_controle.close()
    csv_file.close()

if __name__ == '__main__':
    main()