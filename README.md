# Simulação Estocástica de Protocolos de Streaming: MPEG-DASH vs RTSP/RTP

Este repositório contém a infraestrutura como código (IaC) e os scripts de aplicação desenvolvidos para avaliar e comparar o comportamento dos protocolos de streaming **MPEG-DASH (TCP / Pull)** e **RTSP/RTP (UDP / Push)** sob condições de rede ideais e adversas.

O projeto utiliza o **Mininet** (emulador de redes SDN) para criar cenários topológicos restritivos, injetando parâmetros de latência, perda de pacotes e gargalos de banda, permitindo a extração de telemetria precisa para análise acadêmica.

---

## Arquitetura do Projeto

A simulação é composta por uma topologia em estrela (Cliente -> Switch -> Servidor) e scripts autônomos em Python que emulam o comportamento de servidores de mídia e *players* de vídeo.

### Componentes Principais
* **`topology.py`**: Script mestre do Mininet. Cria os *hosts virtuais* (`h1`, `h2`), o *Switch OpenFlow* (`s1`), aplica as regras de *Traffic Control* (Banda, Latência, Ruído, Fila) e invoca os clientes e servidores de forma automatizada.
* **`server_dash.py`**: Servidor TCP que simula a entrega de mídia via HTTP. Fornece *chunks* estáticos de vídeo em múltiplas resoluções (HIGH: 1MB / LOW: 250KB).
* **`client_dash.py`**: *Player* DASH simulado. Implementa o algoritmo de Adaptação de Bitrate (ABR) e Histerese, monitorando o *Throughput* para decidir dinamicamente qual resolução solicitar.
* **`server_rtsp.py`**: Servidor RTP. Injeta pacotes UDP de tamanho constante (1316 bytes) na rede de forma estática e em rajadas (*Push*), respeitando comandos de controle via canal TCP secundário.
* **`client_rtsp.py`**: *Player* RTP simulado. Consume a mídia em tempo real e monitora o limite físico do *Buffer*. Implementa Histerese (`PAUSE`/`PLAY`) para sinalizar risco de transbordamento ao servidor.

---

##  Cenários de Teste

O projeto foi desenhado para testar a resiliência dos protocolos em 4 cenários baseados na literatura de redes:

1. **Controle (Ideal):** 10 Mbps de Banda | 5ms de Latência | 0% Ruído | Fila BDP curta.
   * *Objetivo:* Validar a linha de base e a estabilidade do ABR e Controle de Fluxo.
2. **Gargalo de Banda (Congestionamento):** 5 Mbps de Banda | 5ms de Latência | 0% Ruído | Fila BDP de 100 pacotes.
   * *Objetivo:* Forçar o *Tail Drop* na fila do roteador e avaliar a concorrência TCP (*Slow Start*) vs. agressividade do UDP.
3. **Rede de Longa Distância (Alta Latência):** 10 Mbps de Banda | 200ms de Latência | 0% Ruído | Fila BDP de 200 pacotes.
   * *Objetivo:* Testar o impacto do RTT prolongado (Handshake TCP) no protocolo DASH e validar a necessidade de buffers profundos (*In-Flight Data*) para o RTSP.
4. **Rede Ruidosa (Interferência):** 10 Mbps de Banda | 5ms de Latência | 5% de Perda Aleatória.
   * *Objetivo:* Diferenciar perda algorítmica de congestionamento real (Simulando degradação de sinal Wi-Fi/4G).

---

##  Requisitos e Dependências

Para executar este laboratório, você precisará de um ambiente Linux (preferencialmente Ubuntu 20.04 ou superior), a configuração dos cenários é feita no arquivo topology.py.

1. **Instalar Mininet e Utilitários de Rede:**
   ```bash
   sudo apt-get update
   sudo apt-get install mininet net-tools iproute2 tcpdump iperf
   sudo python3 topology.py
