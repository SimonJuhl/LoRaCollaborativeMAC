from Medium import Medium
from Node import Node
from Gateway import Gateway


mediums = []
nodes = []

SF = 7
channel = 1
mediums.append(Medium(SF, channel))

gw = Gateway(mediums)

# TODO: Figure out how many mediums we want to create and how we should assign the mediums to the nodes. And on a non-implementation note: How would it make sense to setup nodes in general on channels and SFs? Should we have the GW check load on all channels and SFs and distribute our devices accordingly?

for i in range(2):
    # 10 second period, 30ms offset between each other, 2 byte payload, 0 drift, SF7, channel 1
    nodes.append(Node(i, 10000, i*20, 2, mediums[0], 0, 7, 1))

# for each millisecond in 24 hours
#for ms_index in range(86400000):
for ms_index in range(30000):
    for node in nodes:
        if ms_index == node.next_tx:
            node.transmit()

    for medium in mediums:
        medium.ongoing_transmission_remaining_duration(ms_index)

    gw.update_receivers(ms_index)
    gw.detect_collision_for_ongoing_receptions(ms_index)
    gw.process_transmissions(ms_index)

        #for active_tx in medium.active_transmissions:
        #    print("Node ID:", active_tx['node_id'], "\t Tx ending:", active_tx['end_time'], "\t Time now:", ms_index)


