#!/usr/bin/env python3
"""
topology.py — Smart Sampa: Infraestrutura de Simulação de Streaming
Grupo 3 — ADR/UFABC 2026-Q1

Descrição:
Orquestra a criação da topologia virtual (Mininet), simula o gargalo 
de rede (Traffic Control) e executa as baterias de teste (iPerf, DASH, RTSP).
Finaliza gerando uma análise estocástica baseada na Fila M/M/1.
"""

import os
import time
import json
import subprocess
from datetime import datetime

from mininet.net import Mininet
from mininet.node import Controller, OVSKernelSwitch
from mininet.link import TCLink
from mininet.log import setLogLevel, info
import traceback

# =====================================================================
# BLOCO 1: VARIÁVEIS GLOBAIS E CONFIGURAÇÃO DE CENÁRIOS
# Edite estes valores para testar diferentes estresses na rede
# =====================================================================

# Portas de comunicação da camada de Aplicação
PORT_DASH = 8080
PORT_RTSP = 8554
LOG_DIR = "/tmp/smart_sampa_logs"

# Dicionário de parâmetros da Topologia
# Cenário Padrão: Gargalo de 10 Mbps e Atraso de 5ms.
parametros_smartSP = {
    "h1_ip"           : "10.0.0.1",
    "h2_ip"           : "10.0.0.2",
    
    # Backbone: O núcleo da rede (Rápido e sem restrições)
    "backbone_bw"     : 100,   # Mbps
    "backbone_delay"  : "1ms",
    "backbone_loss"   : 0,     # %
    
    # Bottleneck: O link de acesso problemático
    "bottleneck_bw"   : 10,     # Mbps
    "bottleneck_delay": "5ms",
    "bottleneck_loss" : 0,     # testar perda de rede
}


# =====================================================================
# BLOCO 2: FUNÇÕES AUXILIARES DE TELEMETRIA
# Gerenciamento do diretório de saída e formatação de logs JSON
# =====================================================================
def setup_log_dir():
    """Cria a pasta temporária e gera o carimbo de tempo da sessão."""
    os.makedirs(LOG_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    info(f" Salvando logs em: {LOG_DIR} (sessão {ts})\n")
    return ts

def save_json(data: dict, filename: str):
    """Salva os resultados consolidados (como o cálculo da M/M/1) em formato JSON."""
    path = os.path.join(LOG_DIR, filename)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    info(f"Log salvo: {path}\n")


# =====================================================================
# BLOCO 3: CONSTRUÇÃO DA TOPOLOGIA (MININET)
# Instancia os nós e injeta o controle de tráfego (TC) nos links
# =====================================================================
def buildyTopology():
    """Monta a topologia em haltere: h1 (Servidor) --- s1 (Switch) --- h2 (Cliente)"""
    # Usa o TCLink para permitir a configuração artificial de banda/delay
    net = Mininet(
        controller=Controller,
        link=TCLink,
        switch=OVSKernelSwitch,
        autoSetMacs=True,
        autoStaticArp=True,
    )

    info("Adicionado o controlador OpenFlow padrão\n")
    net.addController("c0")

    info("Criado o Servidor de Mídia (h1)\n")
    h1 = net.addHost("h1", ip=parametros_smartSP["h1_ip"] + "/24")

    info("Criado o Cliente de Monitoramento (h2)\n")
    h2 = net.addHost("h2", ip=parametros_smartSP["h2_ip"] + "/24")

    info("Criado o Roteador/Switch (s1)\n")
    s1 = net.addSwitch("s1")

    info(f"Criando Link Backbone (h1-s1) | {parametros_smartSP['backbone_bw']}Mbps\n")
    net.addLink(
        h1, s1,
        bw    = parametros_smartSP["backbone_bw"],
        delay = parametros_smartSP["backbone_delay"],
        loss  = parametros_smartSP["backbone_loss"],
    )

    info(f"Criando Link Gargalo (s1-h2) | {parametros_smartSP['bottleneck_bw']}Mbps\n")
    net.addLink(
        s1, h2,
        bw    = parametros_smartSP["bottleneck_bw"],
        delay = parametros_smartSP["bottleneck_delay"],
        loss  = parametros_smartSP["bottleneck_loss"],
        max_queue_size = 100,
    )

    return net, h1, h2, s1


# =====================================================================
# BLOCO 4: BATERIA DE TESTES
# Módulos independentes para testar baseline (iPerf), DASH e RTSP
# =====================================================================
def run_connectivity_tests(net, h1, h2, session_ts: str):
    """Gera a linha de base (Baseline). Prova que o gargalo está lá matematicamente."""
    info("\n--- Teste de Conectividade Base ---\n")
    loss = net.pingAll()

    # Afere o Atraso (Delay) real via ICMP
    ping_output = h2.cmd(f"ping -c 20 -i 0.2 {parametros_smartSP['h1_ip']}")
    rtt_line = [l for l in ping_output.split("\n") if "rtt" in l]
    rtt_stats = rtt_line[0] if rtt_line else "N/A"
    info(f"Latência RTT: {rtt_stats}\n")

    # Afere a Largura de Banda Real (Throughput)
    info("\nTestando capacidade do gargalo com iPerf (TCP)...\n")
    h2.cmd('iperf -s -p 5001 &')
    iperf_tcp_raw = h1.cmd(f"iperf -c {parametros_smartSP['h2_ip']} -p 5001 -t 5")
    
    tcp_bw = "N/A"
    for linha in iperf_tcp_raw.split('\n'):
        if "Mbits/sec" in linha or "Kbits/sec" in linha:
            tcp_bw = linha.split()[-2] + " " + linha.split()[-1]
    info(f"Resultado TCP: {tcp_bw}\n")

    info("Testando capacidade do gargalo com iPerf (UDP)...\n")
    h2.cmd('iperf -s -u -p 5002 &')
    # Força a injeção UDP no limite do gargalo configurado
    iperf_udp_raw = h1.cmd(f"iperf -c {parametros_smartSP['h2_ip']} -u -p 5002 -b {parametros_smartSP['bottleneck_bw']}M -t 5")
    
    udp_bw = "N/A"
    for linha in iperf_udp_raw.split('\n'):
        if "Mbits/sec" in linha or "Kbits/sec" in linha:
            udp_bw = linha.split()[-4] + " " + linha.split()[-3]
    info(f"Resultado UDP: {udp_bw}\n")

    h2.cmd('killall -9 iperf')

    results = {
        "session"       : session_ts,
        "ping_loss_pct" : loss,
        "iperf_tcp_mbps": tcp_bw,
        "iperf_udp_mbps": udp_bw,
        "rtt_stats"     : rtt_stats,
        "parametros"    : parametros_smartSP,
    }
    save_json(results, f"connectivity_{session_ts}.json")


def run_dash_experiment(net, h1, h2, session_ts: str, duration: int = 60):
    """Executa a simulação do streaming Adaptativo (MPEG-DASH) sobre TCP."""
    info("\n--- Experimento MPEG-DASH (HTTP/TCP Pull) ---\n")
    log_file = os.path.join(LOG_DIR, f"dash_{session_ts}.csv")

    h1.cmd(
        f"python3 server_dash.py "
        f"--port {PORT_DASH} "
        f"> {LOG_DIR}/server_dash_{session_ts}.log 2>&1 &"
    )
    time.sleep(2) # Aguarda o servidor subir a porta

    info(f"[DASH] Iniciando cliente ABR por {duration}s...\n")
    h2.cmd(
        f"python3 client_dash.py "
        f"--server {parametros_smartSP['h1_ip']} "
        f"--port {PORT_DASH} "
        f"--duration {duration} "
        f"--log {log_file} "
        f"> {LOG_DIR}/client_dash_{session_ts}.log 2>&1"
    )

    info(f"Experimento DASH concluído. Logs em: {log_file}\n")
    h1.cmd("pkill -f server_dash.py")


def run_rtsp_experiment(net, h1, h2, session_ts: str, duration: int = 60):
    """Executa a simulação do streaming legado (RTSP/RTP) via túneis UDP+TCP."""
    info("\n--- Experimento RTSP/RTP (UDP Push) ---\n")
    log_file = os.path.join(LOG_DIR, f"rtsp_{session_ts}.csv")

    h1.cmd(
        f"python3 server_rtsp.py "
        f"--port {PORT_RTSP} "
        f"--media /tmp/media/ "
        f"> {LOG_DIR}/server_rtsp_{session_ts}.log 2>&1 &"
    )
    time.sleep(2)

    info(f"[RTSP] Iniciando cliente receptor por {duration}s...\n")
    h2.cmd(
        f"python3 client_rtsp.py "
        f"--server {parametros_smartSP['h1_ip']} "
        f"--port {PORT_RTSP} "
        f"--duration {duration} "
        f"--log {log_file} "
        f"> {LOG_DIR}/client_rtsp_{session_ts}.log 2>&1"
    )

    info(f"Experimento RTSP concluído. Logs em: {log_file}\n")
    h1.cmd("pkill -f server_rtsp.py")


# =====================================================================
# BLOCO 5: ANÁLISE ANALÍTICA (M/M/1)
# Comprova matematicamente os limites do enfileiramento da rede
# =====================================================================
def run_math_summary(session_ts: str):
    """Calcula estatísticas de fila baseadas no cenário configurado."""
    info("\n--- Análise Matemática (Fila M/M/1) ---\n")

    # Capacidade é a banda do gargalo
    C     = parametros_smartSP["bottleneck_bw"] * 1e6 
    # Assumimos uma taxa de injeção média de 8 Mbps
    lam   = 8e6 
    mu    = C
    rho   = lam / mu

    if rho >= 1.0:
        info("Sistema instável (ρ >= 1)! Fila cresce infinitamente.\n")
    else:
        Lq  = rho**2 / (1 - rho)
        Wq  = Lq / lam
        W   = Wq + (1 / mu)

        info(f"Capacidade (C)   : {C/1e6:.1f} Mbps\n")
        info(f"Taxa de Chegada (λ) : {lam/1e6:.1f} Mbps\n")
        info(f"Utilização (ρ)      : {rho:.4f}  ({rho*100:.1f}%)\n")
        info(f"Fila Média (Lq)     : {Lq:.4f} pacotes\n")
        info(f"Espera (Wq)         : {Wq*1000:.4f} ms\n")

        results = {
            "model"     : "M/M/1",
            "C_bps"     : C,
            "lambda_bps": lam,
            "rho"       : rho,
            "Lq"        : Lq,
            "Wq_ms"     : Wq * 1000,
            "W_ms"      : W  * 1000,
        }
        save_json(results, f"math_mm1_{session_ts}.json")


# =====================================================================
# BLOCO 6: MOTOR DE EXECUÇÃO
# Ponto de entrada do script que orquestra todo o fluxo
# =====================================================================
if __name__ == '__main__':
    setLogLevel('info') 
    print("\n[*] Iniciando o Orquestrador Smart Sampa...\n")
    
    session_ts = setup_log_dir()
    net, h1, h2, s1 = buildyTopology()
    
    try:
        info("\n*** Iniciando a Rede Virtual ***\n")
        net.start()
        
        run_connectivity_tests(net, h1, h2, session_ts)
        run_dash_experiment(net, h1, h2, session_ts, duration=60)
        run_rtsp_experiment(net, h1, h2, session_ts, duration=60)
        
        run_math_summary(session_ts)
        
    except Exception as e:
        print(f"\n[!] ERRO CRÍTICO NA EXECUÇÃO: {e}")
        traceback.print_exc()
    finally:
        info("\n*** Limpando Recursos e Encerrando ***\n")
        net.stop()
        info("\n[+] Orquestração concluída com sucesso!\n")