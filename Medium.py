class Medium:
    def __init__(self, SF, channel):
        self.SF = SF
        self.channel = channel
        self.active_transmissions = []

    def start_transmission(self, node_id, start_time, duration, tx_power, location):
        end_time = start_time + duration
        dict = {'node_id': node_id, 'start_time': start_time, 'end_time': end_time, 'tx_power': tx_power, 'location': location}
        self.active_transmissions.append(dict)

    def ongoing_transmission_remaining_duration(self, clock):
        # iterating backwards to avoid pop causing IndexError
        for i in range(len(self.active_transmissions)-1, -1, -1):
            if self.active_transmissions[i]['end_time'] < clock:
                self.active_transmissions.pop(i)
