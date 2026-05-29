import numpy as np
import pandas as pd
from scipy.signal import medfilt
import matplotlib.pyplot as plt

def decode_differential_edges(input_file, output_file):
    """
    Calculates a differential signal, uses vectorised edge detection 
    to extract tri-level data (+1, -1), groups them by ignoring 5us gaps, 
    and converts to binary to decode 12-pulse trains.
    """
    # 1. Load the raw capture data
    try:
        df = pd.read_csv(input_file)
        time = df.iloc[:, 0].values
        
        # Calculate differential signal: Column 2 minus Column 3
        differential_signal = df.iloc[:, 1].values - df.iloc[:, 2].values
    except FileNotFoundError:
        print(f"Error: Could not locate '{input_file}'.")
        return
    except IndexError:
        print("Error: The CSV must contain at least three columns.")
        return

    # 2. Filter artefacts
    clean_signal = medfilt(differential_signal, kernel_size=5)

    # 3. Edge Detection Logic
    positive_active = (clean_signal > 0.5).astype(int)
    negative_active = (clean_signal < -0.5).astype(int)

    pos_transitions = np.where(np.diff(positive_active) == 1)[0] + 1
    neg_transitions = np.where(np.diff(negative_active) == 1)[0] + 1

    # 4. Compile and sort the detected pulses using vectorised arrays
    times_pos = time[pos_transitions]
    times_neg = time[neg_transitions]

    combined_times = np.concatenate((times_pos, times_neg))
    
    # Store as tri-level data: 1s for positive, -1s for negative
    combined_data = np.concatenate((np.ones(len(times_pos), dtype=int), 
                                    -np.ones(len(times_neg), dtype=int)))

    sort_order = np.argsort(combined_times)

    pulse_times = combined_times[sort_order]
    pulse_data = combined_data[sort_order]
    
    # 5. Group pulses into trains
    # Set threshold to 15us to ignore the 5us inter-pulse spacing 
    # and only split on the ~20us train gaps.
    gap_threshold = 5e3 
    
    trains = []
    current_train = []
    last_time = None
    
    for t, level in zip(pulse_times, pulse_data):
        if not current_train:
            current_train.append(level)
            last_time = t
        else:
            if (t - last_time) > gap_threshold:
                trains.append(current_train[0:12])
                current_train = [level]
            else:
                current_train.append(level)
            last_time = t
            
    if current_train:
        trains.append(current_train[0:12])

    # 6. Convert to binary and decode into decimal values
    decimals = []
    for index, train in enumerate(trains):
        if len(train) == 12:
            # Map the tri-level -1 to binary 0 at the final step
            binary_train = [1 if val == 1 else 0 for val in train]
            
            # Join bits into a string and convert from base-2 to base-10
            bit_string = "".join(str(b) for b in binary_train)
            print(bit_string)
            decimals.append(int(bit_string, 2))
        else:
            print(f"Artefact Warning: Train {index} contains {len(train)} pulses. Expected 12.")
            decimals.append(np.nan) 

    # 7. Output results
    output_df = pd.DataFrame({'Decoded_Decimal': decimals})
    output_df.to_csv(output_file, index=False)
    print(f"Decoding finished. Processed {len(decimals)} train(s). Results saved to '{output_file}'.")
    plt.plot(decimals)
    plt.show()


if __name__ == "__main__":
    decode_differential_edges('raw_signals_capture.csv', 'decoded_serial_data.csv')