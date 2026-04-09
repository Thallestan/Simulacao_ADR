import argparse
import socket

def main():
    # =====================================================================
    # BLOCO 1: RECEBIMENTO DE PARÂMETROS
    # Permite que a porta seja dinamicamente injetada pela topologia (Mininet)
    # =====================================================================
    parser = argparse.ArgumentParser(description="Smart Sampa: DASH Server")
    parser.add_argument('--port', type=int, default=8080, help="Porta TCP do servidor")
    args = parser.parse_args()

    HOST = '0.0.0.0' # Ouve em todas as interfaces de rede disponíveis
    PORT = args.port
    
    # =====================================================================
    # BLOCO 2: DEFINIÇÃO DO PERFIL DE MÍDIA (VÍDEO VIRTUAL)
    # Define o peso exato dos blocos de vídeo (Chunks) para emular o tráfego
    # =====================================================================
    CHUNK_HIGH_SIZE = 1024 * 1024
    CHUNK_LOW_SIZE = 250 * 1024

    # =====================================================================
    # BLOCO 3: INICIALIZAÇÃO DO SOCKET TCP
    # Configura o servidor no paradigma "Pull" (espera o cliente pedir)
    # =====================================================================
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((HOST, PORT))
        s.listen(1)
        print(f"[*] Servidor DASH (Sequenciado) aguardando conexões na porta TCP {PORT}")
        
        
        while True:
            try:
                conn, addr = s.accept()
                print(f"[*] Cliente conectado: {addr}")
                
                with conn:
                    while True:
                        req = conn.recv(1024)
                        if not req: 
                            break 
                        # =====================================================================
                        # BLOCO 4: EMPACOTAMENTO E ENVIO (PROTOCOLO DE APLICAÇÃO)
                        # =====================================================================
                        if b"GET_CHUNK_HIGH" in req:
                            payload = (b'H' * (CHUNK_HIGH_SIZE - 8))
                            conn.sendall(payload)
                            
                        elif b"GET_CHUNK_LOW" in req:
                            payload = (b'L' * (CHUNK_LOW_SIZE - 8))
                            conn.sendall(payload)
                            
            except KeyboardInterrupt:
                print("\n[*] Desligamento manual do servidor DASH.")
                break
            except Exception as e:
                pass

if __name__ == '__main__':
    main()