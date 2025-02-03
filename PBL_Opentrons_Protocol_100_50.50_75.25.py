"""
Author: David Edward Weyland (PhD student)
Purpose: This protocol is designed to automate the mixing and processing of three different photoactive biomaterials
         (e.g., GelMA, HA-NB, PEG-DA) at varying weight percentages (%w/v): 10%, 5%-5%, 7.5%-2.5%. The protocol performs
         aspirate/dispense operations, offset mixing, and transfers to custom microwells on the Opentrons platform.
         
Overview:
1. Material Handling:
   - Material A: Column 1 of custom reservoir
   - Material B: Column 2 of custom reservoir
   - Material C: Column 3 of custom reservoir
2. Mixing:
   - Uses a P20 multi-channel pipette to mix materials with offset positions for turbulence.
3. Transfers:
   - Precise liquid transfers to specified aluminum block and custom microwells.
4. Parameters:
   - Mixing volumes and cycles are customisable for flexibility.

Note: Ensure the labware and pipettes are calibrated before running the protocol. This protocol requires 2 Opentrons temperature modules.
"""

from opentrons import protocol_api
from opentrons.types import Point  # Required for position offsets

metadata = {"apiLevel": "2.21"}

def run(protocol: protocol_api.ProtocolContext):


    # Load labware
    temp_module_1 = protocol.load_module('temperature module gen2', 1)
    temp_module_4 = protocol.load_module('temperature module gen2', 4)


    # Turn on the temperature modules to reach 50C in solutions - set it higher than 50 in order to reach target temperature in the solutions
    temp_module_1.set_temperature(80)
    temp_module_4.set_temperature(80)


    # Custom reservoir in slot 4
    custom_reservoir = temp_module_4.load_labware('custom_reservoir', 4)


    # Use Bio-Rad 96 Well Plate instead of aluminum block (Opentrons does not reognise aluminum block as valid labware)
    aluminum_block_1 = temp_module_1.load_labware('biorad_96_wellplate_200ul_pcr')


    # Custom molds in slots 2 and 5
    custom_microwell_slot2 = protocol.load_labware('custom_sample_holder', 2)


    # Tip racks
    p20_tiprack_slot3 = protocol.load_labware('opentrons_96_filtertiprack_20ul', 3)
    p20_tiprack_slot5 = protocol.load_labware('opentrons_96_filtertiprack_20ul', 5)
    p20_tiprack_slot6 = protocol.load_labware('opentrons_96_filtertiprack_20ul', 6)
    p20_tiprack_slot8 = protocol.load_labware('opentrons_96_filtertiprack_20ul', 8)
    p20_tiprack_slot9 = protocol.load_labware('opentrons_96_filtertiprack_20ul', 9)


    # Pipettes
    p1000_single = protocol.load_instrument(
        'p1000_single_gen2', 'left', tip_racks=None)

    p20_multi = protocol.load_instrument(
        'p20_multi_gen2', 'right', tip_racks=[p20_tiprack_slot3, p20_tiprack_slot5, p20_tiprack_slot6, p20_tiprack_slot8, p20_tiprack_slot9])

    # Slow Liquid Handling - high speed aspiration/dispensing may introduce air bubbles
    p20_multi.flow_rate.aspirate = 3  # Slow aspiration (default ~7.6 µL/s)
    p20_multi.flow_rate.dispense = 4  # Slow dispensing (default ~7.6 µL/s)

    # Blow-out Speed - control how fast pipette expels residual liquid from tip after dispensing
    p20_multi.flow_rate.blow_out = 5 # Reduce blow-out speed (default ~7.6 µL/s)

    # Gantry Speed - reduce mechanical vibrations
    p20_multi.default_speed = 100  # Set default speed for all movements (default ~400 mm/s)

    # Function for refilling columns 1, 2 and 3 of aluminum block with materials A, B and C
    def refill_materials(pipette, reservoir_columns, dest_columns, volume_per_cycle, total_volume):
        """
        Transfer materials from reservoir columns to destination columns.
        Args:
        pipette: The pipette object (e.g., p20_multi).
        reservoir_columns: List of reservoir column indices.
        dest_columns: List of destination column indices.
        volume_per_cycle: Volume to aspirate/dispense in each cycle (µL).
        total_volume: Total volume to transfer to each destination column (µL).
        """
        cycles = total_volume // volume_per_cycle  # Calculate full aspirate/dispense cycles
        for source_idx, dest_idx in zip(reservoir_columns, dest_columns):
            pipette.pick_up_tip()
            for _ in range(cycles):
                pipette.aspirate(volume_per_cycle, custom_reservoir.columns()[source_idx][0])
                pipette.move_to(aluminum_block_1.columns()[dest_idx][0].top(30))
                pipette.dispense(volume_per_cycle, aluminum_block_1.columns()[dest_idx][0])
                pipette.blow_out(aluminum_block_1.columns()[dest_idx][0])
                pipette.move_to(aluminum_block_1.columns()[dest_idx][0].top(30))
            pipette.drop_tip()


    # Function for offset mixing + position control with multi-channel P20 pipette
    def offset_mixing_p20_multi(pipette, location, mix_cycles, total_volume=80):
        """
        Perform offset mixing with a P20 multi-channel pipette.
        Args:
        pipette: The pipette object (e.g., p20_multi).
        location: The well location to perform mixing.
        mix_cycles: Number of mixing cycles.
        total_volume: Total volume to be mixed per cycle (in µL).
        """

    # Define offsets for better mixing (in mm)
        offsets = [Point(x=1, y=0, z=0), Point(x=-1, y=0, z=0), Point(x=0, y=1, z=0), Point(x=0, y=-1, z=0)]
        aspirate_volume = 20  # Maximum aspirate volume per step
        total_steps = total_volume // aspirate_volume # Number of steps per cycle (e.g., 80 µL = 4 steps of 20 µL)

        for cycle in range(mix_cycles):  # Perform multiple mixing cycles
            for offset in offsets:  # Iterate through offsets for turbulence
                for _ in range(total_steps):  # Repeat for the total mixing steps
                    # Move near the bottom for aspiration with an offset
                    pipette.move_to(location.bottom(1).move(offset))  # 1 mm above the bottom
                    pipette.aspirate(aspirate_volume, location)

                    # Move near the center for dispensing with an offset
                    pipette.move_to(location.center().move(offset))  # Dispense at the center of the well
                    pipette.dispense(aspirate_volume, location)
    
    mixing_cycles = 1  # Perform 1 full offset cycle

    def transfer_and_mix_once(pipette, source_columns, dest_column, source_volumes, mixing_cycles):
        """
        Handles the transfer for a destination column using multiple source columns.
        Ensures a tip change after each source column transfer and performs offset mixing at the destination
        only after the final dispensing step.
        Args:
        pipette: The pipette object (e.g., p20_multi).
        source_columns: List of source column indices.
        dest_column: Destination column index.
        volumes: List of total volumes to transfer from each source column (in µL).
        total_volume: Total volume to be mixed at the destination (in µL).
        mixing_cycles: Number of mixing cycles.
        """
       
    # Calculate the total mix volume dynamically
        total_mix_volume = sum(source_volumes)  # Total volume to be mixed in the destination column

        for i, (source, source_volume) in enumerate(zip(source_columns, source_volumes)):  # Iterate through sources and volumes
            pipette.pick_up_tip()  # Pick up a new tip for each source column
            cycles = source_volume // 20  # Determine how many full 20 µL cycles are needed
            remaining = source_volume % 20  # Calculate the remaining volume

        # Perform full 20 µL cycles
            for _ in range(cycles):
                pipette.aspirate(20, aluminum_block_1.columns()[source][0])
                pipette.dispense(20, aluminum_block_1.columns()[dest_column][0])
                pipette.blow_out(aluminum_block_1.columns()[dest_column][0])

        # Handle any remaining volume
            if remaining > 0:
                pipette.aspirate(remaining, aluminum_block_1.columns()[source][0])
                pipette.dispense(remaining, aluminum_block_1.columns()[dest_column][0])
                pipette.blow_out(aluminum_block_1.columns()[dest_column][0])

        # Perform offset mixing ONLY after the last source column transfer
            if i == len(source_columns) - 1:
                offset_mixing_p20_multi(pipette=p20_multi, location=aluminum_block_1.columns()[dest_column][0], mix_cycles=mixing_cycles)
            
            pipette.move_to(aluminum_block_1.columns()[dest_column][0].top(30))
            pipette.drop_tip()  # Drop the tip after finishing transfers (and mixing, if applicable)

    def final_mixing_and_transfer(pipette, aluminum_block, microwell_holder, reservoir, di_water_column, column_range, mix_cycles, transfer_volume):
        """
        Final mixing in aluminum block, transfer of solution, and DI water addition into custom sample holder.
        Handles cases where the custom sample holder has a limited number of columns.
        Args:
        pipette: The pipette object (e.g., p20_multi).
        aluminum_block: Aluminum block labware containing the source columns.
        microwell_holder: Custom sample holder labware for the destination.
        reservoir: Custom reservoir labware containing DI water.
        di_water_column: Column index for DI water in the reservoir.
        column_range: Range of columns in the aluminum block to process (e.g., range(0, 4)).
        total_mix_volume: Total volume of the solution to be mixed (in µL).
        mix_cycles: Number of mixing cycles.
        transfer_volume: Volume to transfer from aluminum block to sample holder (in µL).
        """
        # Remap aluminum block columns to custom microwell columns (0–3 only)
        microwell_columns = range(0, 4)

        for col_idx, microwell_idx in zip(column_range, microwell_columns):
        # Step 1: Mix the solution in the aluminum block
            pipette.pick_up_tip()
            offset_mixing_p20_multi(pipette=pipette, location=aluminum_block.columns()[col_idx][0], mix_cycles = mix_cycles)

        # Step 2: Transfer solution to custom sample holder in steps
            for _ in range(transfer_volume // 20):  # Divide into 20 µL cycles
                pipette.aspirate(20, aluminum_block.columns()[col_idx][0])
                pipette.dispense(20, microwell_holder.columns()[microwell_idx][0])
                pipette.blow_out(microwell_holder.columns()[microwell_idx][0])
            
            pipette.move_to(microwell_holder.columns()[microwell_idx][0].top(30))
            pipette.drop_tip()  # Drop the tip after transferring solution

        # Step 3: Transfer DI water to the custom sample holder
            pipette.pick_up_tip()
            pipette.aspirate(20, reservoir.columns()[di_water_column][0])  # Aspirate 20 µL DI water
            pipette.dispense(20, microwell_holder.columns()[microwell_idx][0])  # Dispense into the custom sample holder
            pipette.move_to(microwell_holder.columns()[microwell_idx][0].top(30))
            pipette.drop_tip()  # Drop the tip after transferring DI water


#############################################################################################################################################################

# PROTOCOL 

# STEP 1: Aspirate and dispense materials into 96-well aluminum block

    # Materials A, B, and C to columns 1, 2, and 3 of aluminum_block_1
    refill_materials(pipette=p20_multi, reservoir_columns=[0, 1, 2], dest_columns=[0, 1, 2], volume_per_cycle=20, total_volume=160)


# STEP 2: Dispense mixtures into columns 4, 5, 6 of PLATE 1 

    # Column 4: 50-50 AB
    transfer_and_mix_once(pipette=p20_multi, source_columns=[0, 1], dest_column=3, source_volumes=[50,50], mixing_cycles = mixing_cycles)

    # Column 5: 50-50 AC
    transfer_and_mix_once(pipette=p20_multi, source_columns=[0, 2], dest_column=4, source_volumes=[50,50], mixing_cycles = mixing_cycles)

    # Column 6: 50-50 BC
    transfer_and_mix_once(pipette=p20_multi, source_columns=[1, 2], dest_column=5, source_volumes=[50,50], mixing_cycles= mixing_cycles)

# STEP 3: Refill Columns 1, 2, 3 of PLATE 1 to 160µL

    # Materials A, B, and C to columns 1, 2, and 3 of aluminum_block_1
    refill_materials(pipette=p20_multi, reservoir_columns=[0, 1, 2], dest_columns=[0, 1, 2], volume_per_cycle=20, total_volume=100)

# STEP 4: Dispense mixtures into columns 7, 8, 9, 10 of Plate 1

    # Column 7: 75-25 AB
    transfer_and_mix_once(pipette=p20_multi, source_columns=[0, 1], dest_column=6, source_volumes=[75,25], mixing_cycles = mixing_cycles)

    # Column 8: 75-25 AC
    transfer_and_mix_once(pipette=p20_multi, source_columns=[0, 2], dest_column=7, source_volumes=[75,25], mixing_cycles = mixing_cycles)

    # Column 9: 75-25 BC
    transfer_and_mix_once(pipette=p20_multi, source_columns=[1, 2], dest_column=8, source_volumes=[75,25], mixing_cycles = mixing_cycles)

    # Column 10: 75-25 CB
    transfer_and_mix_once(pipette=p20_multi, source_columns=[2, 1], dest_column=9, source_volumes=[75,25], mixing_cycles = mixing_cycles)

# STEP 5: Refill Column 1 to 130µL and Columns 2, 3 to 155µL

    # Materials A, B, and C to columns 1, 2, and 3 of aluminum_block_1
    refill_materials(pipette=p20_multi, reservoir_columns=[0, 1, 2], dest_columns=[0, 1, 2], volume_per_cycle=20, total_volume=120)

# STEP 6: Dispense mixtures into columns 11, 12 of Plate 1

    # Column 11: 75-25 CA
    transfer_and_mix_once(pipette=p20_multi, source_columns=[2, 0], dest_column=10, source_volumes=[75,25], mixing_cycles = mixing_cycles)

    # Column 12: 75-25 BA
    transfer_and_mix_once(pipette=p20_multi, source_columns=[1, 0], dest_column=11, source_volumes=[75,25], mixing_cycles = mixing_cycles)


# STEP 7: Pause for Temperature Equilibration

    # Notify user about 10-minute pause
    protocol.comment("Protocol will be paused for 10 minutes to allow for temperature equilibration")

    # Delay the protocol for 10 minutes
    protocol.delay(minutes=10)  # Automatically pause operations for 10 minutes

    # Pause for manual intervention
    protocol.pause("10-minute delay complete. Please perform manual intervention and click 'Resume' to continue.")


# STEP 8: Final Mixing and Transfer into Custom Microwell No. 1

    final_mixing_and_transfer(
    pipette=p20_multi,
    aluminum_block=aluminum_block_1,
    microwell_holder=custom_microwell_slot2,
    reservoir=custom_reservoir,
    di_water_column=3,
    column_range=range(0, 4),  # Aluminum block columns 1–4
    mix_cycles=5,
    transfer_volume=40
)

# STEP 9: Pause for Sample Withdrawal and Characterisation

# Step: Notify user about incubation and manual intervention
    protocol.comment(
    "The protocol will now proceed with a 30-minute incubation period. \n"
    "During this time, please prepare to perform the following steps:\n"
    "1. Remove the current custom microwell from the left slot of the sample holder.\n"
    "2. Flip the sample holder.\n"
    "3. Place a new custom microwell into the left slot of the sample holder.\n"
)
    
# Step: Incubate for 30 minutes
    protocol.delay(minutes=30)

# Step: Pause and wait for user to resume
    protocol.pause("When you are ready, click 'Resume' in the Opentrons App to continue the protocol.")

# Continue with the rest of the protocol

# STEP 10: Final Mixing and Transfer into Custom Microwell No. 2

    final_mixing_and_transfer(
    pipette=p20_multi,
    aluminum_block=aluminum_block_1,
    microwell_holder=custom_microwell_slot2,
    reservoir=custom_reservoir,
    di_water_column=3,
    column_range=range(4, 8),  # Aluminum block columns 4–8
    mix_cycles=5,
    transfer_volume=40
)

# STEP 11: Pause for Sample Withdrawal and Characterisation

# Step: Notify user about incubation and manual intervention
    protocol.comment(
    "The protocol will now proceed with a 30-minute incubation period. \n"
    "During this time, please prepare to perform the following steps:\n"
    "1. Remove the current custom microwell from the left slot of the sample holder.\n"
    "2. Flip the sample holder.\n"
    "3. Place a new custom microwell into the left slot of the sample holder.\n"
)
    
# Step: Incubate for 30 minutes
    protocol.delay(minutes=30)

# Step: Pause and wait for user to resume
    protocol.pause(
    "When you are ready, click 'Resume' in the Opentrons App to continue the protocol."
)

# STEP 12: Final Mixing and Transfer into Microwell No. 3

    final_mixing_and_transfer(
    pipette=p20_multi,
    aluminum_block=aluminum_block_1,
    microwell_holder=custom_microwell_slot2,
    reservoir=custom_reservoir,
    di_water_column=3,
    column_range=range(8, 12),  # Aluminum block columns 8–12
    mix_cycles=5,
    transfer_volume=40
    )
# STEP 13: Pause for Sample Withdrawal and Ntofication of Termination

# Step: Notify user of protocol completion
    protocol.pause(
    "Protocol complete. Please review the results and ensure all necessary steps have been performed.\n"
    "When you are ready, click 'Resume' in the Opentrons App to terminate the protocol."
)

# STEP 14: Termination 

  # Deactivate temperature modules
    temp_module_1.deactivate()
    temp_module_4.deactivate()

# End of protocol message
    protocol.comment("Protocol complete. All temperature modules have been deactivated. You may now safely remove labware and power down the robot. Thank you for using this protocol.")
