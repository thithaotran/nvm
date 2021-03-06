from gate_sequencer import GateSequencer

opcodes = [
    "movv","movd","jmpv","jmpd",
    "cmpv","cmpd","jie",
    "subv","subd","ret",
    "mem","rem","nxt","prv","ref","drf",
    "mref", "mdrf",
    "exit","nop"]

def gflow(to_layer, from_layer):
    """gates for inter-layer information flow"""
    return [(to_layer,from_layer,'u'), (to_layer,to_layer,'d')]

def gprog():
    """gates for program memory (ip and op) layer updates"""
    return gflow('ip','ip') + gflow('opc','ip') + gflow('op1','ip') + gflow('op2','ip')

def flash_instruction_set(nvmnet, verbose=False):
    """
    layers: dict of layers, including:
        gate_output, gate_hidden, ip, opc, op1, op2, op3, cmph, cmpo
    """
    # if verbose:
    #     for name in nvmnet.layers:
    #         print("|%s|=%d"%(name, nvmnet.layers[name].size))
    gate_map, layers, registers = nvmnet.gate_map, nvmnet.layers, nvmnet.registers
    gate_output, gate_hidden = layers['go'], layers['gh']
    gs = GateSequencer(gate_map, gate_output, gate_hidden, layers)

    ### Start executing new instruction
    
    h = gate_hidden.coder.encode('start')
    g = gs.make_gate_output() # start with default gates
    gate_output.coder.encode('start', g)
    g_start, h_start = g.copy(), h.copy()

    g, h = gs.add_transit(
        ungate = gprog(),
        old_gates = g_start, old_hidden = h_start)
    gate_output.coder.encode('load', g)
    gate_hidden.coder.encode('load', h)
    g_load, h_load = g.copy(), h.copy()
    
    # Let opcode bias the gate layer
    g, h = gs.add_transit(ungate = [('gh','opc','u')],
        old_gates = g_load, old_hidden=h_load)

    # Ready to execute instruction
    g_ready, h_ready = g.copy(), h.copy()
    gate_hidden.coder.encode('ready', h_ready)
    gate_output.coder.encode('ready', g_ready)
    
    ###### NOP
    
    # just return to start state
    gs.add_transit(
        new_gates = g_start, new_hidden = h_start,
        old_gates = g_ready, old_hidden = h_ready, opc = 'nop')

    ###### MOVV

    # Let op1 bias the gate layer
    g, h = gs.add_transit(ungate = [('gh','op1','u')],
        old_gates = g_ready, old_hidden = h_ready, opc='movv')
    g_movv, h_movv = g.copy(), h.copy()
    gate_hidden.coder.encode('movv', h_movv)
    gate_output.coder.encode('op1', g_movv)
    for name, register in registers.items():
        # Open flow from op2 to register in op1
        g, h = gs.add_transit(
            ungate = gflow(name, 'op2'),
            old_gates = g_movv, old_hidden = h_movv, op1 = name)
        gate_hidden.coder.encode('movv_'+name, h)
        gate_output.coder.encode('movv_'+name, g)

        # return to start state
        gs.add_transit(
            new_gates = g_start, new_hidden = h_start,
            old_gates = g, old_hidden = h)

    ###### MOVD

    # Let op1 and op2 bias the gate layer
    g, h = gs.add_transit(ungate = [
        ('gh','op1','u'),('gh','op2','u')
        ],
        old_gates = g_ready, old_hidden = h_ready, opc='movd')
    g_movd, h_movd = g.copy(), h.copy()
    gate_hidden.coder.encode('movd', h_movd)
    gate_output.coder.encode('movd', g_movd)
    for from_name, from_register in registers.items():
        for to_name, to_register in registers.items():
            # Open flow between registers
            g, h = gs.add_transit(
                ungate = gflow(to_name, from_name),
                old_gates = g_movd, old_hidden = h_movd,
                op1 = to_name, op2 = from_name)
            gate_hidden.coder.encode('movd_'+to_name+'_'+from_name, h)
            gate_output.coder.encode('movd_'+to_name+'_'+from_name, g)

            # return to start state
            gs.add_transit(
                new_gates = g_start, new_hidden = h_start,
                old_gates = g, old_hidden = h)

    ###### JIE

    # Let co bias the gate layer
    g, h = gs.add_transit(ungate = [('gh','co','u')],
        old_gates = g_ready, old_hidden = h_ready, opc='jie')
    g_jie, h_jie = g.copy(), h.copy()
    gate_hidden.coder.encode('jie', h_jie)
    gate_output.coder.encode('jie', g_jie)

    # If co contains false, just return to start state
    gs.add_transit(
        new_gates = g_start, new_hidden = h_start,
        old_gates = g_jie, old_hidden = h_jie,
        co = 'false')

    # If co contains true, open flow from op1 to ip
    g, h = gs.add_transit(
        ungate = gflow('ip', 'op1'),
        old_gates = g_jie, old_hidden = h_jie,
        co = 'true')
    gate_hidden.coder.encode('jie_true', h)

    # Stabilize ip
    g, h = gs.stabilize(h, num_iters=5)

    # then return to start state
    gs.add_transit(
        new_gates = g_start, new_hidden = h_start,
        old_gates = g, old_hidden = h)

    ###### JMPV

    # Open flow from op1 to ip
    g, h = gs.add_transit(ungate = gflow('ip','op1'),
        old_gates = g_ready, old_hidden = h_ready, opc='jmpv')
    g_jmpv, h_jmpv = g.copy(), h.copy()
    gate_hidden.coder.encode('jmpv', h_jmpv)
    gate_output.coder.encode('ip<op1', g_jmpv)

    # Stabilize ip
    g, h = gs.stabilize(h, num_iters=3)

    # then return to start state
    gs.add_transit(
        new_gates = g_start, new_hidden = h_start,
        old_gates = g, old_hidden = h)

    ###### JMPD

    # Let op1 bias the gate layer
    g, h = gs.add_transit(ungate = [('gh','op1','u')],
        old_gates = g_ready, old_hidden = h_ready, opc='jmpd')
    g_jmpd, h_jmpd = g.copy(), h.copy()
    gate_hidden.coder.encode('jmpd', h_jmpd)
    for register in registers:

        # Open flow from register in op1 to ip
        g, h = gs.add_transit(
            ungate = gflow('ip', register),
            old_gates = g_jmpd, old_hidden = h_jmpd,
            op1 = register)
        g_jmpd_dev, h_jmpd_dev = g.copy(), h.copy()
        gate_hidden.coder.encode('jmpd_'+register, h_jmpd_dev)
        gate_output.coder.encode('jmpd_'+register, g_jmpd_dev)

        # Stabilize ip
        g, h = gs.stabilize(h, num_iters=3)

        # then return to start state
        gs.add_transit(
            new_gates = g_start, new_hidden = h_start,
            old_gates = g, old_hidden = h)

    ###### MEM

    # Let op1 bias the gate layer
    g, h = gs.add_transit(ungate = [('gh','op1','u')],
        old_gates = g_ready, old_hidden = h_ready, opc='mem')
    g_mem, h_mem = g.copy(), h.copy()
    gate_hidden.coder.encode('mem', h_mem)
    for register in registers:

        # Open plasticity from mf to register in op1
        g, h = gs.add_transit(
            ungate = [(register, 'mf', 'l')],
            old_gates = g_mem, old_hidden = h_mem,
            op1 = register)
        g_mem_dev, h_mem_dev = g.copy(), h.copy()
        gate_hidden.coder.encode('mem_'+register, h_mem_dev)
        gate_output.coder.encode('mem_'+register, g_mem_dev)

        # then return to start state
        gs.add_transit(
            new_gates = g_start, new_hidden = h_start,
            old_gates = g_mem_dev, old_hidden = h_mem_dev)

    ###### REM

    # Let op1 bias the gate layer
    g, h = gs.add_transit(ungate = [('gh','op1','u')],
        old_gates = g_ready, old_hidden = h_ready, opc='rem')
    g_rem, h_rem = g.copy(), h.copy()
    gate_hidden.coder.encode('rem', h_rem)
    for register in registers:

        # Open flow from mf to register in op1
        g, h = gs.add_transit(
            ungate = gflow(register, 'mf'),
            old_gates = g_rem, old_hidden = h_rem,
            op1 = register)
        g_rem_dev, h_rem_dev = g.copy(), h.copy()
        gate_hidden.coder.encode('rem_'+register, h_rem_dev)
        gate_output.coder.encode('rem_'+register, g_rem_dev)

        # then return to start state
        gs.add_transit(
            new_gates = g_start, new_hidden = h_start,
            old_gates = g_rem_dev, old_hidden = h_rem_dev)

    ###### NXT

    # Let mf move forward, driving mb
    g, h = gs.add_transit(
        ungate = gflow('mf', 'mf') + gflow('mb', 'mf'),
        old_gates = g_ready, old_hidden = h_ready, opc='nxt')
    g_nxt, h_nxt = g.copy(), h.copy()
    gate_hidden.coder.encode('nxt', h_nxt)
    gate_output.coder.encode('nxt', g_nxt)

    # then return to start state
    gs.add_transit(
        new_gates = g_start, new_hidden = h_start,
        old_gates = g_nxt, old_hidden = h_nxt)

    ###### PRV

    # Let mb move backward, driving mf
    g, h = gs.add_transit(
        ungate = gflow('mb', 'mb') + gflow('mf', 'mb'),
        old_gates = g_ready, old_hidden = h_ready, opc='prv')
    g_prv, h_prv = g.copy(), h.copy()
    gate_hidden.coder.encode('prv', h_prv)
    gate_output.coder.encode('prv', g_prv)

    # then return to start state
    gs.add_transit(
        new_gates = g_start, new_hidden = h_start,
        old_gates = g_prv, old_hidden = h_prv)

    ###### CMPD

    # Let op1 bias the gate layer
    g, h = gs.add_transit(
        ungate = [('gh','op1','u')],
        old_gates = g_ready, old_hidden = h_ready, opc='cmpd')
    g_cmpd, h_cmpd = g.copy(), h.copy()
    gate_hidden.coder.encode('cmpd', h_cmpd)
    gate_output.coder.encode('cmpd', g_cmpd)
    for cmpd_a_name, cmpd_a_register in registers.items():
        # Open flow from register A to ci
        g, h = gs.add_transit(
            ungate = gflow("ci", cmpd_a_name),
            old_gates = g_cmpd, old_hidden = h_cmpd,
            op1 = cmpd_a_name)
        gate_hidden.coder.encode('cmpd_'+cmpd_a_name+'_ci', h)
        gate_output.coder.encode('ci<'+cmpd_a_name, g)

        # Ungate dipole learning from ci to co
        g, h = gs.add_transit(
            ungate = [("co","ci","l")],
            old_gates = g, old_hidden = h)
        gate_hidden.coder.encode('cmpd_'+cmpd_a_name+'_di', h)
        gate_output.coder.encode('cmpd_di', g)
        
        # Let op2 bias the gate layer
        g, h = gs.add_transit(
            ungate = [('gh','op2','u')],
            old_gates = g, old_hidden = h)
        g_cmpd2, h_cmpd2 = g.copy(), h.copy()
        gate_hidden.coder.encode('cmpd2_'+cmpd_a_name, h_cmpd2)
        gate_output.coder.encode('cmpd2', g_cmpd2)
        for cmpd_b_name, cmpd_b_register in registers.items():

            # Open flow from register B to ci
            g, h = gs.add_transit(
                ungate = gflow("ci", cmpd_b_name),
                old_gates = g_cmpd2, old_hidden = h_cmpd2,
                op2 = cmpd_b_name)
            gate_hidden.coder.encode('cmpd_'+cmpd_a_name+'_'+cmpd_b_name+'_ci', h)
            gate_output.coder.encode('ci<'+cmpd_b_name, g)

            # Open flow from ci to co
            g, h = gs.add_transit(
                ungate = gflow("co","ci"),
                old_gates = g, old_hidden = h)
            gate_hidden.coder.encode('cmpd_'+cmpd_a_name+'_'+cmpd_b_name+'_co', h)
            gate_output.coder.encode('co<ci', g)

            # co contains result, return to start state
            gs.add_transit(
                new_gates = g_start, new_hidden = h_start,
                old_gates = g, old_hidden = h)

    ###### CMPV

    # Let op1 bias the gate layer
    g, h = gs.add_transit(
        ungate = [('gh','op1','u')],
        old_gates = g_ready, old_hidden = h_ready, opc='cmpv')
    g_cmpv, h_cmpv = g.copy(), h.copy()
    gate_hidden.coder.encode('cmpv', h_cmpv)
    gate_output.coder.encode('cmpv', g_cmpv)
    for cmpv_a_name, cmpv_a_register in registers.items():
        # Open flow from register A to ci
        g, h = gs.add_transit(
            ungate = gflow("ci", cmpv_a_name),
            old_gates = g_cmpv, old_hidden = h_cmpv,
            op1 = cmpv_a_name)
        gate_hidden.coder.encode('cmpv_'+cmpv_a_name+"_ci", h)
        gate_output.coder.encode('cmpv_'+cmpv_a_name+"_ci", g)

        # Ungate dipole learning from ci to co
        g, h = gs.add_transit(
            ungate = [("co","ci","l")],
            old_gates = g, old_hidden = h)
        gate_hidden.coder.encode('cmpv_'+cmpv_a_name+'_di', h)
        gate_output.coder.encode('cmpv_di', g)
        
        # Open flow from op2 to ci
        g, h = gs.add_transit(
            ungate = gflow("ci", "op2"),
            old_gates = g, old_hidden = h)
        gate_hidden.coder.encode('cmpv_'+cmpv_a_name+'_ci', h)
        gate_output.coder.encode('ci<op2', g)

        # Open flow from ci to co
        g, h = gs.add_transit(
            ungate = gflow("co","ci"),
            old_gates = g, old_hidden = h)
        gate_hidden.coder.encode('cmpv_'+cmpv_a_name+'_co', h)
        gate_output.coder.encode('co<ci', g)

        # co contains result, return to start state
        gs.add_transit(
            new_gates = g_start, new_hidden = h_start,
            old_gates = g, old_hidden = h)

    ###### SUBV

    # Push ip on stack (open learning from sf to ip)
    g, h = gs.add_transit(
        ungate = [('ip', 'sf', 'l')],
        old_gates = g_ready, old_hidden = h_ready, opc='subv')
    g_subv, h_subv = g.copy(), h.copy()
    gate_hidden.coder.encode('subv', h_subv)
    gate_output.coder.encode('subv', g_subv)

    # Advance stack pointer
    g, h = gs.add_transit(
        ungate = gflow('sf', 'sf') + gflow('sb', 'sf'),
        old_gates = g_subv, old_hidden = h_subv)
    g_subv_nxt, h_subv_nxt = g.copy(), h.copy()
    gate_hidden.coder.encode('subv_nxt', h_subv_nxt)
    gate_output.coder.encode('subv_nxt', g_subv_nxt)

    # Open flow from op1 to ip
    g, h = gs.add_transit(ungate = gflow('ip','op1'),
        old_gates = g_subv_nxt, old_hidden = h_subv_nxt)
    g_subv_jmp, h_subv_jmp = g.copy(), h.copy()
    gate_hidden.coder.encode('subv_jmp', h_subv_jmp)

    # Stabilize ip
    g, h = gs.stabilize(h, num_iters=3)

    # then return to start state
    gs.add_transit(
        new_gates = g_start, new_hidden = h_start,
        old_gates = g, old_hidden = h)

    ###### SUBD

    # Push ip on stack (open learning from sf to ip)
    g, h = gs.add_transit(
        ungate = [('ip', 'sf', 'l')],
        old_gates = g_ready, old_hidden = h_ready, opc='subd')
    g_subd, h_subd = g.copy(), h.copy()
    gate_hidden.coder.encode('subd', h_subd)
    gate_output.coder.encode('subd', g_subd)

    # Advance stack pointer
    g, h = gs.add_transit(
        ungate = gflow('sf', 'sf') + gflow('sb', 'sf'),
        old_gates = g_subd, old_hidden = h_subd)
    g_subd_nxt, h_subd_nxt = g.copy(), h.copy()
    gate_hidden.coder.encode('subd_nxt', h_subd_nxt)
    gate_output.coder.encode('subd_nxt', g_subd_nxt)

    # Let op1 bias the gate layer
    g, h = gs.add_transit(
        ungate = [('gh','op1','u')],
        old_gates = g_subd_nxt, old_hidden = h_subd_nxt)
    g_subd_op1, h_subd_op1 = g.copy(), h.copy()
    gate_hidden.coder.encode('subd_op1', h_subd_op1)
    gate_output.coder.encode('gh+op1', g_subd_op1)
    for subd_name, subd_register in registers.items():
        # Open flow from register to ip
        g, h = gs.add_transit(ungate = gflow('ip', subd_name),
            old_gates = g_subd_op1, old_hidden = h_subd_op1,
            op1 = subd_name)
        g_subd_jmp, h_subd_jmp = g.copy(), h.copy()
        gate_hidden.coder.encode('subd_' + subd_name + '_jmp', h_subd_jmp)
    
        # Stabilize ip
        g, h = gs.stabilize(h, num_iters=3)
    
        # then return to start state
        gs.add_transit(
            new_gates = g_start, new_hidden = h_start,
            old_gates = g, old_hidden = h)

    ###### RET

    # Decrement stack pointer (let sb move backward, driving sf)
    g, h = gs.add_transit(
        ungate = gflow('sb', 'sb') + gflow('sf', 'sb'),
        old_gates = g_ready, old_hidden = h_ready, opc='ret')
    g_ret, h_ret = g.copy(), h.copy()
    gate_hidden.coder.encode('ret', h_ret)
    gate_output.coder.encode('ret', g_ret)

    # Open flow from sf to ip
    g, h = gs.add_transit(ungate = gflow('ip','sf'),
        old_gates = g_ret, old_hidden = h_ret)
    g_ret_jmp, h_ret_jmp = g.copy(), h.copy()
    gate_hidden.coder.encode('ret_jmp', h_ret_jmp)

    # # Stabilize ip
    # g, h = gs.stabilize(h, num_iters=3)

    # then return to start state
    gs.add_transit(
        new_gates = g_start, new_hidden = h_start,
        old_gates = g, old_hidden = h)

    ####### REF

    # Let op1 bias the gate layer
    g, h = gs.add_transit(ungate = [('gh','op1','u')],
        old_gates = g_ready, old_hidden = h_ready, opc='ref')
    g_ref, h_ref = g.copy(), h.copy()
    gate_hidden.coder.encode('ref', h_ref)
    for register in registers:

        # Open plasticity from register in op1 to mf and mb
        g, h = gs.add_transit(
            ungate = [('m'+x, register, 'l') for x in "fb"],
            old_gates = g_ref, old_hidden = h_ref,
            op1 = register)
        g_ref_dev, h_ref_dev = g.copy(), h.copy()
        gate_hidden.coder.encode('ref_'+register, h_ref_dev)
        gate_output.coder.encode('ref_'+register, g_ref_dev)

        # then return to start state
        gs.add_transit(
            new_gates = g_start, new_hidden = h_start,
            old_gates = g_ref_dev, old_hidden = h_ref_dev)

    ####### DRF
    
    # Let op1 bias the gate layer
    g, h = gs.add_transit(
        ungate = [('gh','op1','u')],
        old_gates = g_ready, old_hidden = h_ready, opc='drf')
    g_drf, h_drf = g.copy(), h.copy()
    gate_hidden.coder.encode('drf', h_drf)
    gate_output.coder.encode('drf', g_drf)
    for drf_name, drf_register in registers.items():
        # Open flow from register to mf and mb
        g, h = gs.add_transit(
            ungate = gflow("mf", drf_name) + gflow("mb", drf_name),
            old_gates = g_drf, old_hidden = h_drf,
            op1 = drf_name)
        gate_hidden.coder.encode('drf_'+drf_name, h)
        gate_output.coder.encode("mx<" + drf_name, g)

        # return to start state
        gs.add_transit(
            new_gates = g_start, new_hidden = h_start,
            old_gates = g, old_hidden = h)

    ####### MREF

    # Let op1 bias the gate layer
    # Let mb drive mp
    g, h = gs.add_transit(ungate = [('gh','op1','u')] + gflow('mp', 'mb'),
        old_gates = g_ready, old_hidden = h_ready, opc='mref')
    g_mref, h_mref = g.copy(), h.copy()
    gate_hidden.coder.encode('mref', h_mref)

    h_mref_conv = gate_hidden.coder.encode('mref_conv')

    for mref_name, mref_register in registers.items():

        # Open flow from register to mf and mb (perform dereference)
        g, h = gs.add_transit(
            ungate = gflow("mf", mref_name) + gflow("mb", mref_name),
            old_gates = g_mref, old_hidden = h_mref,
            op1 = mref_name)
        gate_hidden.coder.encode('mref_'+mref_name, h)
        gate_output.coder.encode("mref_mx<" + mref_name, g)

        # Open plasticity from mf to mp
        g, h = gs.add_transit(
            ungate = [('mp', 'mf', 'l')],
            old_gates = g, old_hidden = h,
            new_hidden = h_mref_conv)

    # Let mp drive mf and mb
    g, h = gs.add_transit(
        ungate = gflow('mf', 'mp') + gflow('mb', 'mp'),
        old_hidden = h_mref_conv)
    g_mref_end, h_mref_end = g.copy(), h.copy()
    gate_hidden.coder.encode('mref_end', h_mref_end)
    gate_output.coder.encode('mref_end', g_mref_end)

    # then return to start state
    gs.add_transit(
        new_gates = g_start, new_hidden = h_start,
        old_hidden = h_mref_end, old_gates = g_mref_end)

    ####### MDRF

    # Let mf drive mp
    g, h = gs.add_transit(
        ungate = gflow('mp', 'mf'),
        old_gates = g_ready, old_hidden = h_ready, opc='mdrf')
    g_mdrf, h_mdrf = g.copy(), h.copy()
    gate_hidden.coder.encode('mdrf_1', h_mdrf)
    gate_output.coder.encode('mdrf_1', g_mdrf)

    # Let mp drive mf and mb
    g, h = gs.add_transit(
        ungate = gflow('mf', 'mp') + gflow('mb', 'mp'),
        old_gates = g_mdrf, old_hidden = h_mdrf)
    g_mdrf, h_mdrf = g.copy(), h.copy()
    gate_hidden.coder.encode('mdrf_2', h_mdrf)
    gate_output.coder.encode('mdrf_2', g_mdrf)

    # then return to start state
    gs.add_transit(
        new_gates = g_start, new_hidden = h_start,
        old_gates = g_mdrf, old_hidden = h_mdrf)

    weights, biases, residual = gs.flash(verbose)
    return weights, biases

