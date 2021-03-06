import numpy as np
import matplotlib.pyplot as plt
from nvm import make_scaled_nvm
from builtins import input

np.seterr(all='raise')

dsst_programs = {
"dsst":"""

            # sub lookup
            # sub find
            sub doit
            exit

    # full dsst algorithm
            # find next blank
    doit:   sub find
            # move to symbol above
            mov pm up
            sub step
            # lookup in key
            sub lookup
            # find blank again
            sub find
            # write out symbol in temporal cortex
            mov mc tc
            mov mc hold
            # exit
            jmp doit
            

    # Find next blank position
            # go to top left
    find:   mov pm left
            sub tend
            mov pm up
            sub tend
            # go down 3 to first target
            mov pm down
            sub step
            sub step
            sub step
            # loop over rows, columns, check for blank
    loop:   cmp ol _
            jie found
            mov pm right
            sub step
            # check for end of row
            cmp ol +
            jie endrow
            # row not over, repeat
            jmp loop
            # check for end of board
    endrow: mov pm left
            sub step
            mov pm down
            sub step
            cmp ol +
            jie found
            # board not over, repeat on next line left to right
            mov pm left
            sub tend
            # down one more to skip symbols
            mov pm down
            sub step
            # repeat
            jmp loop
    found:  ret

    # look up current symbol in key
    # intended symbol should be in occipital lobe
    # lookup result will be in temporal cortex
            # put current symbol in temporal cortex
    lookup: mov tc ol
            # look left and up to find key
            mov pm left
            sub tend
            mov pm up
            sub tend
            # check current symbol against key
    check:  cmp tc ol
            jie match
            # if no match, step through key
            mov pm right
            sub step
            jmp check
            # if match, put matching digit below in temporal cortex
    match:  mov pm down
            sub step
            mov tc ol
            # lookup done
            ret

    # do one step (move and then hold)
    # intended direction should be in premotor
    step:   mov mc pm
            mov mc hold
            ret

    # move to boundary of dsst area
    # intended direction should be in premotor
            # compare current view with boundary (+)
    tend:   cmp ol +
            jie back
            # if not at boundary yet, keep stepping
            sub step
            jmp tend
            # if at boundary, take one step back
    back:   cmp pm left
            jie left
            cmp pm right
            jie right
            cmp pm down
            jie down
            # one step in opposite direction
    up:     mov pm down
            jmp done
    down:   mov pm up
            jmp done
    right:  mov pm left
            jmp done
    left:   mov pm right
    done:   sub step
            ret

            exit
"""
}

def make_dsst_grid(letters, rows, cols):

    grid = [["+" for c in range(cols+2)] for r in range(2*rows+2)]
    for r in range(rows):
        for c in range(cols):
            if r == 0 and c < len(letters):
                grid[2*r+1][c+1] = letters[c]
                grid[2*r+2][c+1] = str(c)
            else:
                grid[2*r+1][c+1] = letters[np.random.randint(len(letters))]
                grid[2*r+2][c+1] = "_"
    return grid

def make_dsst_nvm(activator_label, tokens=[]):

    nvm = make_scaled_nvm(
        register_names = ["ol", "tc", "pm", "mc"],
        programs = dsst_programs,
        orthogonal=True,
        scale_factor=1.0,
        extra_tokens=tokens)
    
    print("|ip|=%d, |r|=%d"%(nvm.net.layers['ip'].size, nvm.net.layers['ol'].size))
    
    return nvm

if __name__ == "__main__":
    
    letters = list('abcd')
    # explicitly convert to list for python3
    digits = list(map(str,range(len(letters))))
    grid = make_dsst_grid(letters, 3, len(letters))
    print("\n".join([" ".join(g) for g in grid]))
    # raw_input('.')

    # _ is blank space
    # + is grid boundary
    tokens = ["up","left","down","right","_","+"] + letters + digits

    # nvm = make_dsst_nvm("tanh", tokens)
    nvm = make_dsst_nvm("logistic", tokens)
    # changed from raw_input to input for python3
    input('.')

    show_layers = [
        ["ip"] + ["op"+x for x in "c12"] +\
        ["sf","sb"] + ["co","ci"] +\
        nvm.register_names,
    ]
    show_tokens = True
    show_corrosion = False
    show_gates = False

    grid_row, grid_col = 1, 1
    moved = False
    grids = [(grid_row, grid_col, [list(g) for g in grid])]
    
    nvm.assemble(dsst_programs, other_tokens=tokens, verbose=2)
    nvm.load("dsst", {
        "mc": "hold"
    })

    history = []
    start_t = []
    trace = []
    for t in range(32000):
    # for t in range(10):
    
        # Action
        motion = nvm.decode_layer('mc')
        if not motion == 'hold' and not moved:
            if motion == 'left' and grid_col > 0: grid_col -= 1
            if motion == 'right' and grid_col < len(grid[0])-1: grid_col += 1
            if motion == 'up' and grid_row > 0: grid_row -= 1
            if motion == 'down' and grid_row < len(grid)-1: grid_row += 1
            if motion not in ['left','right','up','down']:
                grid[grid_row][grid_col] = motion
            moved = True
            grids.append((grid_row, grid_col, [list(g) for g in grid]))
        if motion == 'hold': moved = False

        # Perception
        nvm.net.activity['ol'] = nvm.net.layers['ol'].coder.encode(grid[grid_row][grid_col])

        ### show state and tick
        # if True:
        # if t % 2 == 0 or nvm.net.at_exit():
        if nvm.at_start() or nvm.at_exit():
            if nvm.at_start():
                start_t.append(t)
                trace_st = " ".join([
                    nvm.net.layers[name].coder.decode(nvm.net.activity[name])
                    for name in ['ip','opc','op1','op2']])
                trace.append(trace_st)
            print('t = %d'%t)
            print(nvm.net.state_string(show_layers, show_tokens, show_corrosion, show_gates))

            for r in range(len(grid)):
                for c in range(len(grid[r])):
                    if r == grid_row and c == grid_col:
                        grid[r][c] += "!"
                    else:
                        grid[r][c] += " "
            print("\n".join([" ".join(g) for g in grid]))
            for r in range(len(grid)):
                for c in range(len(grid[r])):
                    grid[r][c] = grid[r][c][:-1]

            # raw_input(".")
        if nvm.at_exit():
            break
        nvm.net.tick()

        history.append(dict(nvm.net.activity))

    # ### Grid history
    # for i, (r, c, grid_i) in enumerate(grids):
    #     grid_i[r][c] += "!"
    #     print("*** GRID %d ***"%i)
    #     print("At %d, %d"%(r,c))
    #     print("\n".join([" ".join(g) for g in grid_i]))
    #     grid_i[r][c] = grid_i[r][c][:-1]
    #     # raw_input('...')
    
    # print("*** execution trace ***")
    # for t in trace:
    #     print(t)

    ### raster plot
    max_hist = 8000
    if len(history) > max_hist:
        t_off = len(history)-max_hist
        history = history[t_off:]
    else:
        t_off = 0
    A = np.zeros((sum([
        nvm.net.layers[name].size for sl in show_layers for name in sl]),
        len(history)))
    for h in range(len(history)):
        A[:,[h]] = np.concatenate([history[h][k] for sl in show_layers for k in sl],axis=0)
    
    start_t = [t - t_off for t in start_t if t >= t_off]
    xt = start_t
    xl = []
    for t in start_t:
        ops = []
        for op in ["opc","op1","op2"]:
            tok = nvm.net.layers[op].coder.decode(history[t][op])
            ops.append("" if tok in ["null","?"] else tok)
        xl.append("\n".join([str(t+t_off)]+ops))
    yt = np.array([history[0][k].shape[0] for sl in show_layers for k in sl])
    yt = yt.cumsum() - yt/2
    
    act = nvm.net.layers["gh"].activator
    plt.figure()
    plt.imshow(A, cmap='gray', vmin=act.off, vmax=act.on, aspect='auto')
    plt.xticks(xt, xl)
    plt.yticks(yt, [k for sl in show_layers for k in sl])
    plt.tight_layout()
    plt.show()
    
