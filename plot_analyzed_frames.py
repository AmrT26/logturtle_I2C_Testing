import pandas as pd
import matplotlib.pyplot as plt


def plot_nonzero_data(csv_path="analyzed_frames.csv"):
    df = pd.read_csv(csv_path)

    if df.empty:
        print(f"No data found in {csv_path}")
        return

    data_col = df.columns[0]
    nonzero = df[df[data_col] != 0].copy()

    if nonzero.empty:
        print("No non-zero values found")
        return

    indices = nonzero.index.to_numpy()
    values = nonzero[data_col].to_numpy()

    plt.figure(figsize=(10, 4))
    plt.plot(indices, values, marker='o', linestyle='-', linewidth=1.0)
    plt.xlabel("Index")
    plt.ylabel(data_col)
    plt.title(f"{data_col} (non-zero values) vs index")
    plt.grid(True, alpha=0.4)
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    plot_nonzero_data()
