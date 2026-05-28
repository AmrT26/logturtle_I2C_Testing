import numpy as np
import pandas as pd
from scipy.signal import medfilt

def decode_differential_edges(input_file, output_file):
    """
    Calculates a differential signal and uses specific edge detection 
    to extract binary data and decode 12-pulse trains.
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
    # The median filter strips out the brief sampling drop-outs 
    # without shifting or distorting the actual pulse edges.
    clean_signal = medfilt(differential_signal, kernel_size=5)

    # 3. Edge Detection Logic
    # Identify states based on a +/- 0.5 threshold
    positive_active = (clean_signal > 0.5).astype(int)
    negative_active = (clean_signal < -0.5).astype(int)

    # np.diff() outputs a 1 ONLY when the state changes from 0 to 1.
    # For positive_active, this is the rising edge from 0 to 1.
    # For negative_active, this is the falling edge from 0 to -1.
    # Returns to zero will output -1, which we ignore entirely.
    pos_transitions = np.where(np.diff(positive_active) == 1)[0] + 1
    neg_transitions = np.where(np.diff(negative_active) == 1)[0] + 1

    # 4. Compile and sort the detected pulses
    pulses = []
    
    # Append all binary 1s (rising edges to positive)
    for idx in pos_transitions:
        pulses.append((time[idx], 1))
        
    # Append all binary 0s (falling edges to negative)
    for idx in neg_transitions:
        pulses.append((time[idx], 0))

    # Sort all pulses chronologically by their timestamp
    pulses.sort(key=lambda x: x[0])

    # 5. Group pulses into trains
    # Adjust this threshold if your time units are not in seconds (e.g., use 15 for us)
    gap_threshold = 15e-6 
    
    trains = []
    current_train = []
    last_time = None
    
    for t, bit in pulses:
        if not current_train:
            current_train.append(bit)
            last_time = t
        else:
            if (t - last_time) > gap_threshold:
                # Gap indicates the start of a new pulse train
                trains.append(current_train)
                current_train = [bit]
            else:
                current_train.append(bit)
            last_time = t
            
    if current_train:
        trains.append(current_train)

    # 6. Decode into decimal values
    decimals = []
    for index, train in enumerate(trains):
        if len(train) == 12:
            # Join bits into a string and convert from base-2 to base-10
            bit_string = "".join(str(b) for b in train)
            decimals.append(int(bit_string, 2))
        else:
            print(f"Artefact Warning: Train {index} contains {len(train)} pulses. Expected 12.")
            decimals.append(np.nan) # Mark invalid trains to maintain row alignment

    # 7. Output results
    output_df = pd.DataFrame({'Decoded_Decimal': decimals})
    output_df.to_csv(output_file, index=False)
    print(f"Decoding finished. Processed {len(decimals)} train(s). Results saved to '{output_file}'.")


if __name__ == "__main__":
    # Ensure the filenames match your working directory
    decode_differential_edges('raw_signals_capture.csv', 'decoded_serial_data.csv')