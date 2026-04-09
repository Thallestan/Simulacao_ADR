import argparse
import socket
import threading
import time

# Variáveis globais para compartilhamento de estado entre as threads
estado_transmissao = "PAUSE" 
cliente_addr = None

def main():
    # =====================================================================
    # BLOCO 1: RECEBIMENTO DE PARÂMETROS
    # =====================================================================
    parser = argparse.ArgumentParser(description="Smart Sampa: RTSP Server")
    parser.add_argument('--port', type=int, default=8554, help="Porta TCP RTSP")
    parser.add_argument('--media', type=str, default='/tmp/media/', help="Diretorio de mídia")
    args = parser.parse_args()

    HOST = '0.0.0.0'
    PORT_RTSP = args.port
    PORT_RTP = args.port + 1 # RTP usa a porta adjacente superior
    
    # =====================================================================
    # BLOCO 2: PERFIL DA MÍDIA (UDP PUSH)
    # Define o tamanho do pacote para evitar fragmentação no IP (MTU)
    # =====================================================================
    CHUNK_SIZE = 1316 # tamanho padrão
    DUMMY_DATA = b'RTP_VIDEO_PAYLOAD_' * (CHUNK_SIZE // 18)

    # =====================================================================
    # BLOCO 3: CANAL DE CONTROLE (VIA DE SINALIZAÇÃO TCP)
    # Canal "Out-of-Band" dedicado apenas para comandos de reprodução
    # =====================================================================
    def canal_controle_tcp():
        global estado_transmissao, cliente_addr
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s_tcp:
            s_tcp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s_tcp.bind((HOST, PORT_RTSP))
            s_tcp.listen(1)
            print(f"[*] Servidor de Controle RTSP rodando na porta TCP {PORT_RTSP}")
            
            conn, addr = s_tcp.accept()
            cliente_addr = (addr[0], PORT_RTP) 
            
            with conn:
                while True:
                    data = conn.recv(1024)
                    if not data: break
                    cmd = data.decode('utf-8').strip()
                    
                    if "PAUSE" in cmd:
                        estado_transmissao = "PAUSE"
                        print(f"[*] Comando RTSP: PAUSE de {addr[0]}. Interrompendo UDP.")
                    elif "PLAY" in cmd:
                        estado_transmissao = "PLAY"
                        print(f"[*] Comando RTSP: PLAY de {addr[0]}. Inundando rede com UDP.")

    # =====================================================================
    # BLOCO 4: CANAL DE DADOS (TRANSMISSÃO RTP VIA UDP)
    # O paradigma "Push": O servidor empurra dados sem esperar confirmação
    # =====================================================================
    def envio_dados_udp():
        global estado_transmissao, cliente_addr
        seq_num = 0  
        
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s_udp:
            while True:
                if estado_transmissao == "PLAY":
                    try:
                        # =======================================================
                        # TRANSMISSÃO EM LOTE (BURST) - ALF
                        # Dispara 70 pacotes de 1316 bytes de uma vez  
                        # =======================================================
                        for _ in range(70):
                            pacote = f"{seq_num}|".encode('utf-8') + DUMMY_DATA
                            s_udp.sendto(pacote[:CHUNK_SIZE], cliente_addr)
                            seq_num += 1
                        
                        time.sleep(0.1)
                        
                    except Exception as e:
                        print(f"[-] Erro UDP: {e}")

    # =====================================================================
    # BLOCO 5: ORQUESTRAÇÃO DE THREADS
    # Roda as duas vias (Controle e Dados) simultaneamente
    # =====================================================================
    threading.Thread(target=canal_controle_tcp, daemon=True).start()
    threading.Thread(target=envio_dados_udp, daemon=True).start()
    
    try:
        while True: time.sleep(1) 
    except KeyboardInterrupt:
        print("\n[*] Servidor RTSP Desligado.")

if __name__ == '__main__':
    main()