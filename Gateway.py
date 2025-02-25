class RadioReceiver:
    def __init__(self, receiver_id):
        self.receiver_id = receiver_id
        self.current_medium = None
        self.locked_until = 0

    # check if the receiver is free
    def is_available(self, current_time):
        return current_time >= self.locked_until

    # lock receiver onto a transmission until it ends
    def lock_onto_signal(self, medium, end_time):
        self.current_medium = medium
        self.locked_until = end_time

    # free up receiver when transmission is done
    def release(self):
        self.current_medium = None
        self.locked_until = 0


class Gateway:
    def __init__(self, mediums, num_receivers=8):
        self.mediums = mediums
        self.receivers = [RadioReceiver(i) for i in range(num_receivers)]


    '''
    For each medium check if there is one ongoing transmission that has just started. Otherwise, skip to next medium
    If only one ongoing transmission, find available radio receiver and lock onto transmission
    '''
    # TODO: Implement collision logic of paper: "When LoRaWAN Frames Collide (Delft University of Technology)"
    def process_transmissions(self, current_time):
        # TODO: instead of checking one medium after the other, collect all active transmissions and randomly choose one to lock onto
        for medium in self.mediums:
            active_transmissions = []

            # collect active transmissions on this medium
            for t in medium.active_transmissions:
                active_transmissions.append(t)

            medium_handled = False

            for receiver in self.receivers:
                if receiver.current_medium == medium:
                    medium_handled = True
                    break

            # if transmission on medium is already being received, check next medium
            if medium_handled:
                continue

            if not active_transmissions:
                continue  # no active transmissions on this medium
            # TODO: this is not the correct behavior
            elif len(active_transmissions) > 1:
                print(f"Collision detected on Medium (SF={medium.SF}, Channel={medium.channel}) at time {current_time}")
                continue
            # TODO: this is not the correct behavior
            elif active_transmissions[0]['start_time'] != current_time:
                print(f"Not locking onto transmission at time {current_time} because receiver did not catch the beginning of the packet at time {active_transmissions[0]['start_time']}")
                continue

            free_receiver = None

            # find an available receiver
            for receiver in self.receivers:
                if receiver.is_available(current_time):
                    free_receiver = receiver
                    break

            if free_receiver is not None:
                # lock onto the transmission
                tx = active_transmissions[0]
                free_receiver.lock_onto_signal(medium, tx["end_time"])
                print(f"Receiver {free_receiver.receiver_id} locked onto Medium (SF={medium.SF}, Channel={medium.channel}) until {tx['end_time']}")
            else:
                print(f"No receivers available at time {current_time}")


    def detect_collision_for_ongoing_receptions(self, current_time):
        for receiver in self.receivers:
            if not receiver.is_available(current_time):
                if len(receiver.current_medium.active_transmissions) > 1:
                    print(f"Collision detected on Medium (SF={receiver.current_medium.SF}, Channel={receiver.current_medium.channel}) at time {current_time}. Releasing receiver...")
                    receiver.release()


    def update_receivers(self, current_time):
        """Free up receivers if their transmission has ended."""
        for receiver in self.receivers:
            if not receiver.is_available(current_time):
                continue
            if receiver.current_medium:
                print(f"Receiver {receiver.receiver_id} released from Medium (SF={receiver.current_medium.SF}, Channel={receiver.current_medium.channel})")
                receiver.release()
