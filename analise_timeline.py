import os
import glob
import pandas as pd
import json

# =====================================================================
# BLOCO 1: CONFIGURAÇÕES E FUNÇÕES AUXILIARES
# Define o diretório de trabalho e as rotinas de limpeza de dados
# =====================================================================
LOG_DIR = '/tmp/smart_sampa_logs'

def obter_arquivo_recente(padrao):
    """Busca o log mais atual gerado pela topologia do Mininet."""
    arquivos = sorted(glob.glob(os.path.join(LOG_DIR, padrao)))
    return arquivos[-1] if arquivos else None

def filtrar_eventos_importantes(lista_eventos):
    """
    Filtro de Ruído: Remove logs contínuos (como o consumo normal do player) 
    e mantém apenas as transições de estado, perdas e estouros de memória.
    """
    eventos_ignorados = ['Status Buffer Continuo', 'Download Concluido', 'Playback']
    eventos_filtrados = [e for e in lista_eventos if pd.notna(e) and e not in eventos_ignorados]
    return " | ".join(list(dict.fromkeys(eventos_filtrados)))

def main():
    print("="*60)
    print(" GERADOR DE TIMELINE - SMART SAMPA (ADR/UFABC)".center(60))
    print("="*60)

    # =====================================================================
    # BLOCO 2: LEITURA DE METADADOS (JSON)
    # Extrai o contexto matemático (M/M/1) e físico (iPerf) do experimento
    # =====================================================================
    json_conn = obter_arquivo_recente('connectivity_*.json')
    json_math = obter_arquivo_recente('math_mm1_*.json')

    if json_conn and json_math:
        with open(json_conn, 'r') as f:
            dados_rede = json.load(f)
        with open(json_math, 'r') as f:
            dados_math = json.load(f)
            
        print("\n[MÉTRICAS DO GARGALO E iPERF]")
        print(f"- Banda Física (C)       : {dados_math.get('C_bps', 0) / 1e6:.1f} Mbps")
        print(f"- Latência (RTT ICMP)    : {dados_rede.get('rtt_stats', 'N/A')}")
        print(f"- iPerf TCP Real         : {dados_rede.get('iperf_tcp_mbps', 'N/A')}")
        print(f"- iPerf UDP Real         : {dados_rede.get('iperf_udp_mbps', 'N/A')}")
        print(f"- Perda Fila M/M/1 (Lq)  : {dados_math.get('Lq', 0):.2f} pacotes aguardando\n")

    # =====================================================================
    # BLOCO 3: CARREGAMENTO E DISCRETIZAÇÃO DOS LOGS (CSV)
    # Converte os tempos quebrados em milissegundos para Segundos Inteiros
    # =====================================================================
    csv_dash = obter_arquivo_recente('dash_*.csv')
    csv_rtsp = obter_arquivo_recente('rtsp_*.csv')

    if not csv_dash or not csv_rtsp:
        print("[!] Erro: Faltam os arquivos CSV do DASH ou RTSP.")
        return

    df_dash = pd.read_csv(csv_dash)
    df_rtsp = pd.read_csv(csv_rtsp)

    # Filtra o primeiro segundo (Warm-up / Cold Start)
    df_dash = df_dash[df_dash['Tempo_s'] >= 1.0].copy()
    df_rtsp = df_rtsp[df_rtsp['Tempo_s'] >= 1.0].copy()

    # Truncamento de tempo
    df_dash['Segundo'] = df_dash['Tempo_s'].astype(int)
    df_rtsp['Segundo'] = df_rtsp['Tempo_s'].astype(int)

    # =====================================================================
    # BLOCO 4: AGRUPAMENTO DE SÉRIES E CÁLCULO DE ESTATÍSTICAS
    # Resume todos os eventos ocorridos dentro do mesmo segundo
    # =====================================================================
    dash_agrupado = df_dash.groupby('Segundo').agg(
        DASH_Buffer_Medio=('Tamanho_Buffer', 'mean'), # A ocupação média da RAM no segundo
        DASH_Qualidade=('Qualidade', 'last'),         # O estado final da qualidade no segundo
        DASH_Chegada_s=('Tempo_Download_s', lambda x: pd.to_numeric(x, errors='coerce').max()),
        DASH_Eventos=('Evento', lambda x: filtrar_eventos_importantes(x))
    ).reset_index()

    rtsp_agrupado = df_rtsp.groupby('Segundo').agg(
        RTSP_Buffer_Medio=('Tamanho_Buffer_Pacotes', 'mean'),
        RTSP_Eventos=('Evento', lambda x: filtrar_eventos_importantes(x))
    ).reset_index()

    # =====================================================================
    # BLOCO 5: INTERPOLAÇÃO DE DADOS (FORWARD FILL + BACKWARD FILL)
    # Resolve buracos temporais esticando o último estado válido para frente (ffill)
    # =====================================================================
    tempo_maximo = max(df_dash['Segundo'].max(), df_rtsp['Segundo'].max())
    df_base = pd.DataFrame({'Segundo': range(1, int(tempo_maximo) + 1)})

    # Mescla o DASH com a régua perfeita
    dash_continuo = pd.merge(df_base, dash_agrupado, on='Segundo', how='left')
    
    # Aplica a dupla interpolação (ffill e bfill) em todas as métricas de estado contínuo
    dash_continuo['DASH_Buffer_Medio'] = dash_continuo['DASH_Buffer_Medio'].ffill().bfill().round(1)
    dash_continuo['DASH_Qualidade'] = dash_continuo['DASH_Qualidade'].ffill().bfill()
    dash_continuo['DASH_Chegada_s'] = dash_continuo['DASH_Chegada_s'].ffill().bfill()
    
    # Eventos não são contínuos, então só recebem tracinho '-' se não existirem
    dash_continuo['DASH_Eventos'] = dash_continuo['DASH_Eventos'].fillna('-')
    dash_continuo.loc[dash_continuo['DASH_Eventos'] == '', 'DASH_Eventos'] = '-'

    # Mescla o RTSP com a régua perfeita
    rtsp_continuo = pd.merge(df_base, rtsp_agrupado, on='Segundo', how='left')
    rtsp_continuo['RTSP_Buffer_Medio'] = rtsp_continuo['RTSP_Buffer_Medio'].ffill().bfill().round(1)
    
    rtsp_continuo['RTSP_Eventos'] = rtsp_continuo['RTSP_Eventos'].fillna('-')
    rtsp_continuo.loc[rtsp_continuo['RTSP_Eventos'] == '', 'RTSP_Eventos'] = '-'

    # Consolida os dois protocolos
    timeline = pd.merge(dash_continuo, rtsp_continuo, on='Segundo', how='outer')

    # =====================================================================
    # BLOCO 6: EXPORTAÇÃO E VISUALIZAÇÃO
    # Salva os dados processados para uso no artigo e imprime um resumo
    # =====================================================================
    output_csv = os.path.join(LOG_DIR, 'timeline_consolidada.csv')
    timeline.to_csv(output_csv, index=False)
    
    print("="*130)
    print(f"{'Seg':<4} | {'DASH Buffer':<11} | {'Qualidade':<9} | {'Chegada(s)':<10} | {'Eventos Especiais DASH':<30} || {'RTSP Buffer':<11} | {'Eventos Especiais RTSP'}")
    print("-" * 130)
    
    for _, row in timeline.iterrows():
        tem_evento_dash = row['DASH_Eventos'] != '-'
        tem_evento_rtsp = row['RTSP_Eventos'] != '-'
        
        # Mostra a linha no terminal se for um múltiplo de 5 ou se houver um alarme crítico
        if tem_evento_dash or tem_evento_rtsp or int(row['Segundo']) % 5 == 0:
            seg = str(row['Segundo'])
            d_buf = str(row['DASH_Buffer_Medio'])
            d_qual = str(row['DASH_Qualidade'])
            
            # Formata a string do tempo de chegada para exibição clara
            d_chegada = row['DASH_Chegada_s']
            d_chegada_str = f"{d_chegada:.3f}s" if isinstance(d_chegada, float) else str(d_chegada)
            
            d_evt = str(row['DASH_Eventos'])[:30]
            r_buf = str(row['RTSP_Buffer_Medio'])
            r_evt = str(row['RTSP_Eventos'])
            
            print(f"{seg:<4} | {d_buf:<11} | {d_qual:<9} | {d_chegada_str:<10} | {d_evt:<30} || {r_buf:<11} | {r_evt}")

    print("-" * 130)
    print(f"\n[+] Timeline processada via Interpolação (Forward Fill). Salva em: {output_csv}")

if __name__ == '__main__':
    main()