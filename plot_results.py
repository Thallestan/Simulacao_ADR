import os
import glob
import pandas as pd
import matplotlib.pyplot as plt

LOG_DIR = '/tmp/smart_sampa_logs'

def main():
    print("[*] Buscando os logs mais recentes...")
    dash_files = sorted(glob.glob(os.path.join(LOG_DIR, 'dash_*.csv')))
    rtsp_files = sorted(glob.glob(os.path.join(LOG_DIR, 'rtsp_*.csv')))

    if not dash_files or not rtsp_files:
        print("[!] Erro: Não encontrei os logs na pasta.")
        return

    latest_dash = dash_files[-1]
    latest_rtsp = rtsp_files[-1]
    print(f"[*] Analisando DASH: {os.path.basename(latest_dash)}")
    print(f"[*] Analisando RTSP: {os.path.basename(latest_rtsp)}")

    df_dash = pd.read_csv(latest_dash)
    df_rtsp = pd.read_csv(latest_rtsp)

    # Filtra o primeiro segundo (Warm-up / Cold Start)
    df_dash = df_dash[df_dash['Tempo_s'] >= 1.0]
    df_rtsp = df_rtsp[df_rtsp['Tempo_s'] >= 1.0]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))
    fig.suptitle('COMPARAÇÃO DE PROTOCOLOS (DASH vs RTSP)', fontsize=16, fontweight='bold')

    # ==========================================
    # GRÁFICO 1: DASH (Pull / TCP)
    # ==========================================
    ax1.plot(df_dash['Tempo_s'], df_dash['Tamanho_Buffer'], label='Ocupação do Buffer', color='blue', linewidth=2)
    ax1.axhline(y=15, color='red', linestyle='--', label='Gatilho de Pausa (15)')
    ax1.axhline(y=5, color='orange', linestyle='--', label='Gatilho de Retomada (5)')
    
    # Eventos Visuais do DASH
    pausas_dash = df_dash[df_dash['Evento'] == 'Pausa (Buffer Full)']
    retomadas = df_dash[df_dash['Evento'] == 'Retomada (Buffer Low)']
    subidas = df_dash[df_dash['Evento'].str.contains('LOW->HIGH', na=False)]
    descidas = df_dash[df_dash['Evento'].str.contains('HIGH->LOW', na=False)]
    perdas_dash = df_dash[df_dash['Evento'].str.contains('Perda de Rede', na=False)]

    ax1.scatter(pausas_dash['Tempo_s'], pausas_dash['Tamanho_Buffer'], color='red', s=60, label='Mecanismo: Pausou Download', zorder=5)
    ax1.scatter(retomadas['Tempo_s'], retomadas['Tamanho_Buffer'], color='blue', marker='*', s=120, label='Mecanismo: Retomou Download', zorder=5)
    ax1.scatter(subidas['Tempo_s'], subidas['Tamanho_Buffer'], color='green', marker='^', s=100, label='ABR: Decidiu subir Qualidade', zorder=6)
    ax1.scatter(descidas['Tempo_s'], descidas['Tamanho_Buffer'], color='darkorange', marker='v', s=100, label='ABR: Decidiu baixar Qualidade', zorder=6)

    ax1.set_title('Modelo Moderno: MPEG-DASH (Lógica Híbrida ABR + Histerese)', fontsize=14)
    ax1.set_ylabel('Tamanho da Fila (Pacotes)')
    ax1.grid(True, linestyle=':', alpha=0.7)
    
    # LEGENDA 
    ax1.legend(loc='center left', bbox_to_anchor=(1.02, 0.5), fontsize=10)

    # ==========================================
    # GRÁFICO 2: RTSP/RTP (Push / UDP)
    # ==========================================
    ax2.plot(df_rtsp['Tempo_s'], df_rtsp['Tamanho_Buffer_Pacotes'], label='Ocupação do Buffer', color='purple', linewidth=2)
    ax2.axhline(y=2000, color='black', linestyle=':', label='Limite Físico (RAM Max - 2000)')
    ax2.axhline(y=1500, color='red', linestyle='--', alpha=0.6, label='Gatilho de Risco (High - 1500)')
    ax2.axhline(y=500, color='green', linestyle='--', alpha=0.6, label='Gatilho Seguro (Low - 500)')
    
    # Eventos Visuais do RTSP
    pausas_rtsp = df_rtsp[df_rtsp['Evento'].str.contains('PAUSE', na=False)]
    plays_rtsp = df_rtsp[df_rtsp['Evento'].str.contains('PLAY', na=False)]
    perdas_rede = df_rtsp[df_rtsp['Evento'].str.contains('Perda de Rede', na=False)]
    descartes_ram = df_rtsp[df_rtsp['Evento'].str.contains('Overflow', na=False)]
    
    ax2.scatter(pausas_rtsp['Tempo_s'], pausas_rtsp['Tamanho_Buffer_Pacotes'], color='red', marker='v', s=80, label='Enviou RTSP PAUSE (Risco)', zorder=5)
    ax2.scatter(plays_rtsp['Tempo_s'], plays_rtsp['Tamanho_Buffer_Pacotes'], color='green', marker='^', s=80, label='Enviou RTSP PLAY (Seguro)', zorder=5)
    ax2.scatter(perdas_rede['Tempo_s'], perdas_rede['Tamanho_Buffer_Pacotes'], color='darkorange', marker='x', s=60, label='RTP: Pacote dropado (Rede)', zorder=6)
    ax2.scatter(descartes_ram['Tempo_s'], descartes_ram['Tamanho_Buffer_Pacotes'], color='black', marker='X', s=80, label='RTP: Descarte Físico (RAM)', zorder=6)

    ax2.set_title('Modelo Legado: RTSP/RTP (UDP Push)', fontsize=14)
    ax2.set_xlabel('Tempo (Segundos)', fontsize=12)
    ax2.set_ylabel('Tamanho da Fila (Pacotes)')
    ax2.grid(True, linestyle=':', alpha=0.7)
    
    # LEGENDA 
    ax2.legend(loc='center left', bbox_to_anchor=(1.02, 0.5), fontsize=10)

    plt.tight_layout()
    output_img = os.path.join(LOG_DIR, 'grafico_comparativo.png')
    plt.savefig(output_img, dpi=300, bbox_inches='tight')
    
    print(f"\n[*] SUCESSO! Gráfico salvo em: {output_img}")

if __name__ == '__main__':
    main()