#  Arquitetura de Streaming para Smart Cities: Avaliação DASH vs RTSP/RTP

Este repositório contém a infraestrutura como código (IaC) e os scripts de aplicação desenvolvidos para avaliar e comparar o comportamento dos protocolos de streaming **MPEG-DASH (TCP / Pull)** e **RTSP/RTP (UDP / Push)** sob condições de rede ideais e adversas.

---

##  Contexto de Negócio: O Caso Smart Sampa

Este projeto foi modelado para validar a arquitetura de transporte de vídeo de um ecossistema de Cidade Inteligente, inspirado nas demandas do projeto **Smart Sampa** (Prefeitura de São Paulo). 

A premissa de negócio **não é o monitoramento ao vivo (Live)**, mas sim a recuperação de **Mídia Armazenada (Video on Demand - VoD)**. Imagine o cenário: um operador no Centro de Operações (COPOM/CGC) precisa buscar e reproduzir a **gravação de uma câmera de segurança** de rua para analisar um acidente de trânsito ocorrido horas atrás. 

Se a infraestrutura de rede da cidade estiver congestionada ou com interferência, qual protocolo garante a melhor recuperação da evidência?
* **O modelo legado (RTSP/UDP)** entrega o fluxo rapidamente, mas corre o risco de perder pacotes, exibindo uma gravação corrompida (artefatos na tela) no exato momento da colisão dos veículos.
* **O modelo moderno (MPEG-DASH/TCP)** garante a integridade da evidência. Se a rede estrangular, ele adapta a resolução dinamicamente (ABR) para evitar travamentos, garantindo que o operador consiga assistir ao incidente sem perder quadros cruciais da investigação.

---

##  Arquitetura do Projeto

A simulação utiliza o **Mininet** (emulador de redes SDN) para criar cenários topológicos urbanos restritivos, injetando parâmetros de latência, perda de pacotes e gargalos de banda, permitindo a extração de telemetria precisa.

### Componentes Principais
* **`topology.py`**: Script mestre do Mininet. Cria os *hosts virtuais* (`h1` como Servidor de Gravações, `h2` como Terminal do Operador), aplica as regras de rede metropolitana (Banda, Latência, Ruído) e invoca as transmissões.
* **`server_dash.py`**: Servidor TCP que simula o banco de dados de vídeos. Fornece *chunks* de gravações em múltiplas resoluções (HIGH: 1MB / LOW: 250KB).
* **`client_dash.py`**: *Player* DASH do operador. Implementa o algoritmo de Adaptação de Bitrate (ABR), monitorando a rede para decidir dinamicamente qual resolução solicitar.
* **`server_rtsp.py`**: Servidor RTP. Injeta pacotes UDP de tamanho constante (1316 bytes) na rede de forma estática e em rajadas (*Push*).
* **`client_rtsp.py`**: *Player* RTP do operador. Consume a mídia e monitora o *Buffer*, implementando Histerese (`PAUSE`/`PLAY`) para sinalizar risco de transbordamento ao servidor central.

---

##  Cenários de Teste

O projeto submete a busca pelas gravações urbanas a 4 cenários baseados na literatura de redes:

1. **Controle (Rede Dedicada Ideal):** 10 Mbps de Banda | 5ms de Latência | 0% Ruído | Fila BDP curta.
   * *Objetivo:* Validar a linha de base e a estabilidade da recuperação da câmera em condições perfeitas.
2. **Gargalo de Banda (Congestionamento Urbano):** 5 Mbps de Banda | 5ms de Latência | 0% Ruído | Fila BDP de 100 pacotes.
   * *Objetivo:* Emular uma rede metropolitana saturada (Tail Drop) e avaliar a sobrevivência do DASH vs. o colapso cego do UDP.
3. **Rede de Longa Distância (Link de Backhaul):** 10 Mbps de Banda | 200ms de Latência | 0% Ruído | Fila BDP de 200 pacotes.
   * *Objetivo:* Testar a recuperação de uma câmera extremamente distante (Alto RTT) e o impacto do *Handshake* TCP nas gravações.
4. **Rede Ruidosa (Câmera conectada via 4G/Wi-Fi):** 10 Mbps de Banda | 5ms de Latência | 5% de Perda Aleatória.
   * *Objetivo:* Simular interferência eletromagnética comum em ruas e avaliar a ineficiência do TCP (Falso Congestionamento) diante do UDP.

---

##  Requisitos e Dependências

Para executar este laboratório, você precisará de um ambiente Linux (preferencialmente Ubuntu 20.04 ou superior), para alterar o cenário, basta editar o gargalo no arquivo topology.py.

1. **Instalar Mininet e Utilitários de Rede:**
   ```bash
   sudo apt-get update
   sudo apt-get install mininet net-tools iproute2 tcpdump iperf
   sudo python3 topology.py
