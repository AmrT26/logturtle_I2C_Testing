import pandas as pd
import numpy as np
import matplotlib.pyplot as plt


TIME_TO_FIRST_PULSE_NS = 1110
DELAYS_NS = [400, 430, 460, 460, 400, 420, 435, 450, 450, 450, 420]

try:
    df = pd.read_csv("raw_signals_capture.csv")
except FileNotFoundError:
    print("Error : The file 'raw_signals_capture.csv' cannot be found.")
    exit()

df['Clock_Edge'] = df['DIO2_Clock'].diff()
rising_edges = df[df['Clock_Edge'] == 1].index.tolist()

if len(rising_edges) < 11:
    print(f"Warning : only {len(rising_edges)} periods found.")
    df_slice = df
    edges_to_process = rising_edges
else:
    index_fin = rising_edges[10]
    df_slice = df.iloc[:index_fin + 50]
    edges_to_process = rising_edges[:10]

time_ns = df_slice['Time_ns'].to_numpy()
dio0 = df_slice['DIO0_Data'].to_numpy()
dio1 = df_slice['DIO1_Comp'].to_numpy()
clock = df_slice['DIO2_Clock'].to_numpy()

sample_period_ns = time_ns[1] - time_ns[0]
total_len = len(df)

sample_times = []
sample_y_dio0 = []
sample_y_dio1 = []

for edge_idx in edges_to_process:
    current_offset_ns = TIME_TO_FIRST_PULSE_NS

    for bitIdx in range(12):
        if bitIdx > 0:
            current_offset_ns += DELAYS_NS[bitIdx - 1]

        target_index = edge_idx + int(round(current_offset_ns / sample_period_ns))

        if target_index < len(df_slice):
            t_capture = df_slice.iloc[target_index]['Time_ns']
            val_dio0 = df_slice.iloc[target_index]['DIO0_Data']
            val_dio1 = df_slice.iloc[target_index]['DIO1_Comp']

            sample_times.append(t_capture)
            sample_y_dio0.append(val_dio0 + 1.2)
            sample_y_dio1.append(val_dio1)

# 4. Génération du graphique
plt.figure(figsize=(15, 8))

# Tracé des vagues de signaux continus
plt.step(time_ns, clock + 2.5, where='mid', color='r', linewidth=2, label='DIO2 (Clock)')
plt.step(time_ns, dio0 + 1.2, where='mid', color='b', linewidth=2, label='DIO0 (Data)')
plt.step(time_ns, dio1, where='mid', color='g', linewidth=2, label='DIO1 (Comp)')

# AJOUT DES CROIX ROUGES AUX INSTANTS DE CAPTURE
if sample_times:
    plt.scatter(sample_times, sample_y_dio0, color='red', marker='x', s=80, zorder=5,
                label='Instants de capture (Échantillons)')
    plt.scatter(sample_times, sample_y_dio1, color='red', marker='x', s=80, zorder=5)

# Lignes verticales violettes pour repérer chaque début de trame (front montant de la clock)
for edge_idx in edges_to_process:
    plt.axvline(x=df.iloc[edge_idx]['Time_ns'], color='purple', linestyle='--', alpha=0.4)

# Configuration esthétique
plt.title('Decoding validation: The red crosses indicate where the code samples the bits', fontsize=14,
          fontweight='bold')
plt.xlabel('Time (Nanosecondes)', fontsize=12)
plt.ylabel('Signals', fontsize=12)

plt.yticks([0.5, 1.7, 3.0], ['DIO 1 (Comp)', 'DIO 0 (Data)', 'DIO 2 (Clock)'], fontsize=11)
plt.grid(True, linestyle=':', alpha=0.7)
plt.legend(loc='upper right', fontsize=11)

plt.tight_layout()
plt.show()