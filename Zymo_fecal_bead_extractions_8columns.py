def get_values(*names):
    import json
    _all_values = json.loads("""{"num_col":8,"prewash_buff_vol":300,"elute_buff_vol":55,"engage_height":6.7,"gdna_buff_vol":300,"m300_mount":"right"}""")
    return [_all_values[n] for n in names]


from opentrons.types import Point
import math

metadata = {
    'protocolName': 'Zymo Quick-DNA Fecal/Soil Microbe 96 Magbead Kit, 8 columns',
    'author': 'Rami Farawi <rami.farawi@opentrons.com>',
    'source': 'Custom Protocol Request',
    'apiLevel': '2.12'
}


def run(ctx):

    [num_col, prewash_buff_vol, elute_buff_vol, engage_height,
        gdna_buff_vol, m300_mount] = get_values(  # noqa: F821
        "num_col", "prewash_buff_vol", "elute_buff_vol", "engage_height",
            "gdna_buff_vol", "m300_mount")

    if not 1 <= num_col <= 12:
        raise Exception("Enter a column number 1-12")

    prewash_buff_vol = int(prewash_buff_vol)
    gdna_buff_vol = int(gdna_buff_vol)

    # load module
    mag_mod = ctx.load_module('magnetic module gen2', 10)
    mag_plate = mag_mod.load_labware('vwr_96_wellplate_1000ul')

    # load labware
    reag_res = ctx.load_labware('usascientific_12_reservoir_22ml', 1)
    tipracks = [ctx.load_labware('opentrons_96_filtertiprack_200ul', slot)
                for slot in [4, 5, 7, 8, 9]]
    elute_plate = ctx.load_labware('nest_96_wellplate_100ul_pcr_full_skirt', 6)
    # elute_buff = ctx.load_labware('usascientific_12_reservoir_22ml', 6)
    waste_res = ctx.load_labware('nest_1_reservoir_195ml', 11)

    # pipettes
    m300 = ctx.load_instrument('p300_multi_gen2', m300_mount,
                               tip_racks=tipracks)

    # mapping
    waste = waste_res.wells()[0]
    num_bind_buff_wells = math.ceil(num_col/3)
    bind_buff = reag_res.wells()[:4][:num_bind_buff_wells]
    bind_beads = reag_res.wells()[4]
    num_prewash_wells = math.ceil(num_col/6)
    prewash_buff = reag_res.wells()[5:7][:num_prewash_wells]
    num_gdna_wells = math.ceil(num_col/3)
    gdna_wash_buff = reag_res.wells()[7:11][:num_gdna_wells]
    elute_buff = reag_res.wells()[11]
    samples = mag_plate.rows()[0][:num_col]
    airgap = 10

    def pick_up_on_slot(slot):
        m300.starting_tip = ctx.loaded_labwares[slot].well('A1')
        m300.pick_up_tip()

    ctx.comment('\n\nDISPENSING 600ul BINDING BUFFER TO SAMPLES\n')
    pick_up_on_slot(4)
    for i, (source_trough, col) in enumerate(zip(
                                                bind_buff*num_col*3,
                                                samples*3)):
        if i > 0:
            m300.dispense(airgap, source_trough.top())
        m300.aspirate(200, source_trough)
        m300.dispense(200, col.top(z=3), rate=0.8)
        m300.air_gap(airgap)
    m300.drop_tip()

    ctx.comment('\n\nADDING BEADS TO SAMPLES\n')
    pick_up_on_slot(4)
    m300.mix(10, 100, bind_beads.bottom(z=2))
    for i, col in enumerate(samples):
        if i > 0:
            m300.dispense(airgap, bind_beads.top())
        m300.mix(8, 75, bind_beads.bottom(z=2))
        m300.aspirate(25, bind_beads.bottom(z=2))
        m300.air_gap(airgap)
        m300.dispense(25+airgap, col.top(z=3), rate=0.8)
        m300.blow_out()
        m300.air_gap(airgap)
    m300.drop_tip()

    ctx.pause('''
    Seal plate and place on rotator. Rotate at low speed for 10 minutes.
    Spin-down plate, unseal, and place back on mag deck.
    Select "Resume" in the Opentrons app to continue.
    ''')

    ctx.home()
    mag_mod.engage(height_from_base=engage_height-2.5)
    ctx.delay(minutes=2)

    ctx.comment('\n\nREMOVING DNA/RNA SHIELD SUPERNATANT\n')
    for index, s_col in enumerate(samples):
        side = -1 if index % 2 == 0 else 1
        pick_up_on_slot(7)
        aspirate_loc = s_col.bottom(z=1).move(
                Point(x=(s_col.diameter/2-2)*side))

        for _ in range(5):
            if _ > 0:
                m300.dispense(airgap, s_col.top().move(
                        Point(x=(s_col.diameter/2-2)*side)))
            m300.aspirate(170, aspirate_loc, rate=0.33)
            m300.dispense(170, waste.bottom(25), rate=0.8)
            m300.air_gap(airgap)
        m300.drop_tip()

    mag_mod.disengage()
    
    ctx.pause('''
    Check to see whether all of the supernatent has been removed before resuming protocol.
    ''')


    ctx.comment('\n\nDISPENSING PRE-WASH BUFFER TO SAMPLES\n')
    m300.flow_rate.dispense = 0.8*m300.flow_rate.dispense
    pick_up_on_slot(5)
    for source_trough, col in zip(prewash_buff*num_col*6, samples):
        m300.transfer(prewash_buff_vol,
                      source_trough,
                      col.top(z=3),
                      new_tip='never',
                      air_gap=10,
                      rate=0.8)
    ctx.home()
    mag_mod.engage(height_from_base=engage_height-2.5)
    ctx.delay(minutes=2)
    m300.flow_rate.dispense = 2.5*m300.flow_rate.dispense

    ctx.comment('\n\nREMOVING PRE-WASH SUPERNATANT\n')
    for index, s_col in enumerate(samples):
        side = -1 if index % 2 == 0 else 1
        if not m300.has_tip:
            pick_up_on_slot(5)
        aspirate_loc = s_col.bottom(z=1).move(
                Point(x=(s_col.diameter/2-2)*side))

        for _ in range(2):
            if _ > 0:
                m300.dispense(airgap, s_col.top().move(
                        Point(x=(s_col.diameter/2-2)*side)))
            m300.aspirate(prewash_buff_vol/2+10, aspirate_loc, rate=0.33)
            m300.dispense(prewash_buff_vol/2+10, waste.bottom(25))
            m300.air_gap(airgap)
        m300.drop_tip(ctx.loaded_labwares[7].rows()[0][index])

    mag_mod.disengage()

    m300.flow_rate.dispense = 0.8*m300.flow_rate.dispense
    for i in range(2):
        ctx.comment('\n\nDISPENSING gDNA BUFFER TO SAMPLES\n')
        pick_up_on_slot(4)
        for source_trough, col in zip(gdna_wash_buff*num_col, samples):
            m300.transfer(gdna_buff_vol,
                          source_trough,
                          col.top(z=3),
                          air_gap=10,
                          new_tip='never',
                          rate=0.8,
                          blow_out=False)
        m300.drop_tip()
        ctx.home()
        mag_mod.engage(height_from_base=engage_height-2.5)
        ctx.delay(minutes=2)

        ctx.comment('\n\nREMOVING gDNA SUPERNATANT FROM WELLS\n')
        for index, s_col in enumerate(samples):
            side = -1 if index % 2 == 0 else 1
            if not m300.has_tip:
                m300.pick_up_tip(ctx.loaded_labwares[7].rows()[0][index])
            aspirate_loc = s_col.bottom(z=1).move(
                    Point(x=(s_col.diameter/2-2)*side))

            for _ in range(2):
                if _ > 0:
                    m300.dispense(airgap, s_col.bottom(z=1).move(
                            Point(x=(s_col.diameter/2-2)*side)))
                m300.aspirate(gdna_buff_vol/2+10, aspirate_loc, rate=0.33)
                m300.dispense(gdna_buff_vol/2+10, waste.bottom(35))
                m300.air_gap(airgap)
            if i == 0:
                m300.drop_tip(ctx.loaded_labwares[7].rows()[0][index])
            else:
                m300.drop_tip()
        if i == 0:
            mag_mod.disengage()
    m300.flow_rate.dispense = 1*m300.flow_rate.dispense

    tips = []
    for tiprack in tipracks:
        for col in tiprack.rows()[0]:
            if col.has_tip:
                tips.append(col)


    ctx.pause("""Dry beads for 30 minutes.
                 Select Resume on the Opentrons app to continue when ready""")
    mag_mod.disengage()
    
    ctx.comment('\n\nADDING ELUTION BUFFER AND MIXING\n')
    for i, col in enumerate(samples):
        pick_up_on_slot(9)
        if i > 0:
            m300.dispense(airgap, elute_buff.top())
        m300.aspirate(elute_buff_vol, elute_buff)
        m300.air_gap(airgap)
        m300.dispense(elute_buff_vol+airgap, col.bottom(z=2), rate=0.8)
        m300.mix(25, 40, col)
        m300.air_gap(airgap)
        #m300.drop_tip()
        m300.drop_tip(ctx.loaded_labwares[8].rows()[0][i])

    ctx.home()
    mag_mod.engage(height_from_base=engage_height-2.5)
    ctx.delay(minutes=2)

    ctx.comment('\n\nCOLLECTING ELUATE\n')

    for index, (s_col, d_col) in enumerate(zip(samples,
                                               elute_plate.rows()[0])):
        side = -1 if index % 2 == 0 else 1
        pick_up_on_slot(8)
        aspirate_loc = s_col.bottom(z=2).move(
                Point(x=(s_col.diameter/2-2)*side))
        if index > 0:
            m300.dispense(airgap, s_col.top().move(
                    Point(x=(s_col.diameter/2-2)*side)))
        m300.aspirate(elute_buff_vol-2, aspirate_loc, rate=0.6)
        m300.dispense(elute_buff_vol, d_col.bottom(z=2), rate=0.6)
        m300.air_gap(airgap)
        m300.drop_tip()
