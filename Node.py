import math

# TODO: Handle case where next transmission planned is sooner than the ending of current transmission

class Node:
    def __init__(self, ID, T, t_i, P, medium, drift=0, SF=7, channel=1, BW=125, CR=5, crc=False, explicit_header=False, TxPower=14, location=(0, 0)):
        self.ID = ID

        self.T = T
        self.t_i = t_i
        self.P = P              # payload size
        #self.preamble_len = 8   # symbols

        self.next_tx = t_i
        self.drift = drift

        self.medium = medium
        self.SF = SF
        self.channel = channel
        self.BW = BW
        self.CR = CR
        self.crc = crc
        self.explicit_header = explicit_header

        self.tx_power = TxPower
        self.location = location

    # Calculations based on:    https://www.rfwireless-world.com/calculators/LoRaWAN-Airtime-calculator.html
    # Same results as:          https://avbentem.github.io/airtime-calculator/ttn/eu868/4,12
    def calculate_time_on_air(self):
        symbol_time = (2 ** self.SF) / self.BW              # Time for one symbol
        n_preamble = 8 + 4.25                               # Preamble symbols (default 8 + 4.25 fixed part)
        t_preamble = n_preamble * symbol_time               # Preamble duration

        # Payload symbol calculations
        payload_bit = 8 * self.P                            # Convert payload size to bits
        payload_bit -= 4 * self.SF                          # Reduce 4*SF from bits
        payload_bit += 8                                    # Additional overhead
        payload_bit += 16 if self.crc else 0                # Add CRC length (16 bits)
        payload_bit += 20 if self.explicit_header else 0    # Add header length (20 bits)
        payload_bit = max(payload_bit, 0)

        payload_symbols = math.ceil(payload_bit / (4 * self.SF)) * self.CR
        payload_symbols += 8                                # Fixed 8-symbol overhead

        t_payload = payload_symbols * symbol_time           # Payload duration
        total_time = t_preamble + t_payload

        return round(total_time, 3)                         # Return time-on-air in milliseconds

    def transmit(self):
        duration = self.calculate_time_on_air()
        self.medium.start_transmission(self.ID, self.next_tx, duration, self.tx_power, self.location)
        self.next_tx = self.next_tx + self.T                               # Calculate next transmission time
