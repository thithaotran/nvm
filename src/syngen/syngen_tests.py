import sys
sys.path.append('../nvm')

from nvm import NVM
from activator import tanh_activator
from learning_rules import rehebbian
from tests import *

from syngen_nvm import *
from op_net import *
from syngen import Network, Environment
from syngen import get_cpu, get_gpus, interrupt_engine

import numpy as np
from random import random, sample, choice

def test_syngen(tester, programs, names, traces, memory=None, tokens=[], num_registers=1, verbose=0):
    """
    Assemble all programs
    run all programs in list of names
    memory = (pointers, values)
    """

    vm = tester._make_vm(num_registers, tokens=tokens)
    if memory is not None: vm.initialize_memory(*memory)

    vm.assemble(programs, verbose=0)

    ### BUILD NETWORK ####
    syn_net = tester._make_syngen_nvm(vm)

    for name, trace in zip(names, traces):
        if verbose > 0:
            print()
            print(name)

        vm.load(name, trace[0])
        syn_net.initialize_activity(vm.net)

        ### SET UP VALIDATION CALLBACK ####
        class TestState:
            t = 0
            unk_count = 0
            start = False
            failed = False

        def callback(layer_name, data):
            if layer_name == "gh":
                state = vm.net.layers["gh"].coder.decode(data)

                if state == "start":
                    TestState.start = True
                    TestState.t += 1
                    #print("\n%d" % TestState.t)
                else:
                    TestState.start = False

                if state == "?":
                    if TestState.unk_count > 20:
                        print("Gate mechanism derailed!")
                        interrupt_engine()
                        TestState.failed = True
                    TestState.unk_count += 1
                else:
                    TestState.unk_count = 0

            elif TestState.start:
                state = vm.net.layers[layer_name].coder.decode(data)
                #print(layer_name, state)

                if TestState.t < len(trace):
                    trace_t = trace[TestState.t]

                    if layer_name in trace_t and state != trace_t[layer_name]:
                        print("Trace mismatch!")
                        print(TestState.t, layer_name, state, trace_t[layer_name])
                        interrupt_engine()
                        TestState.failed = True

        ### BUILD ENVIRONMENT ####
        output_layers = vm.net.layers.keys() if verbose else []

        syn_env = tester._make_syngen_env(vm)
        syn_env.add_visualizer("nvm", output_layers)
        syn_env.add_printer(vm.net, output_layers)
        syn_env.add_custom_output("nvm",
            ["gh"] + vm.register_names, "validator", callback)

        ### CHECK INITIAL STATE ###
        for r in vm.register_names:
            if r in trace[0]:
                state = syn_net.decode_output(r, vm.net.layers[r].coder)
                if state != trace[0][r]:
                    syn_net.free()
                    print("Trace mismatch!")
                    print(0, r, state, trace[0][r])
                    return False

        ### RUN SYNGEN ENGINE ###
        report = syn_net.run(syn_env, {
            "multithreaded" : True,
            "worker threads" : 0,
            "verbose" : verbose})

        if verbose:
            print(report)

        if TestState.failed:
            syn_net.free()
            return False

    syn_net.free()
    return True

class SyngenNVMTestCase(NVMTestCase):

    def _make_syngen_nvm(self, vm):
        return SyngenNVM(vm.net)

    def _make_syngen_env(self, vm):
        syn_env = SyngenEnvironment()
        syn_env.add_checker(vm.net)
        return syn_env

    def _test(self, programs, names, traces,
            memory=None, tokens=[], num_registers=1, verbose=0):
        self.assertTrue(test_syngen(
            self, programs, names, traces,
            memory, tokens, num_registers, verbose))

    def _make_vm(self, num_registers, tokens):
        orthogonal = False
        layer_shape = (16,16) if orthogonal else (32,32)
        pad = 0.0001
        activator, learning_rule = tanh_activator, rehebbian
        register_names = ["r%d"%r for r in range(num_registers)]

        return NVM(layer_shape,
            pad, activator, learning_rule, register_names,
            shapes={}, tokens=tokens, orthogonal=orthogonal)


class SyngenNVMArithTestCase(ut.TestCase):
    in_range = range(-1,10)
    out_range = range(-9,10)
    arith_opdef = make_arith_opdef(in_range=in_range, out_range=out_range)
    unary_opdef = make_unary_opdef(in_range=in_range, out_range=out_range)
    comp_opdef = make_comp_opdef(in_range=in_range)
    all_tokens = [t
        for op in [arith_opdef, unary_opdef, comp_opdef] for t in op.tokens]

    def _make_syngen_nvm(self, vm):
        return SyngenNVM(vm.net,
            [OpNet(vm.net, self.arith_opdef, ["r0", "r1"], ["r0", "r1"], "r2"),
             OpNet(vm.net, self.unary_opdef, ["r1"], ["r0", "r1"], "r2"),
             OpNet(vm.net, self.comp_opdef, ["r0", "r1"], ["r1"], "r2")])

    def _make_syngen_env(self, vm):
        syn_env = SyngenEnvironment()

        def callback(name, data):
            if "input" in name:
                print("")
            print(name, data)

        op = "comp"
        #syn_env.add_custom_output(op,
        #    ["%s_%s" % (op, suffix) for suffix in "input", "hidden", "output"],
        #    "test", callback)

        return syn_env

    def _test(self, programs, names, traces,
            memory=None, tokens=[], num_registers=1, verbose=0):
        self.assertTrue(test_syngen(
            self, programs, names, traces,
            memory, tokens, num_registers, verbose))

    def _make_vm(self, num_registers, tokens):
        orthogonal = True
        layer_shape = (16,16) if orthogonal else (32,32)
        pad = 0.0001
        activator, learning_rule = tanh_activator, rehebbian
        register_names = ["r%d"%r for r in range(num_registers)]

        return NVM(layer_shape,
            pad, activator, learning_rule, register_names,
            shapes={}, tokens=tokens, orthogonal=orthogonal)

    # @ut.skip("")
    def test_squash_op(self):

        program = """
        start:  mov r2 +
                nop
                mov r2 A
                nop
                mov r2 +
                nop
                exit
        """
        trace = [
            {},
            {"r2": "+"    },
            {"r2": "null" }, # squash
            {"r2": "A"    },
            {"r2": "A"    }, # no change
            {"r2": "+"    },
            {"r2": "null" }, # squash
        ]

        self._test({"test":program}, ["test"], [trace],
            tokens = ["A"] + self.all_tokens,
            num_registers=3, verbose=0)


    def _test_op(self, opcode, opdef, from_a=None, from_b=None):

        # Default to all input values
        if from_a is None: from_a = self.in_range
        if from_b is None: from_b = self.in_range

        # Ensure string inputs
        from_a = list(str(x) for x in from_a)
        from_b = list(str(x) for x in from_b)

        # Ensure two functions
        # For unary operations, thread first argument through
        try:
            fs = opdef.operations[opcode]
            f0,f1 = fs
        except ValueError:
            f0 = lambda x,y : x
            f1 = fs[0]

        # Ensure each function can take two arguments
        try: f0("0", "0")
        except TypeError:
            t0 = f0
            f0 = lambda x,y: t0(y)
        except: pass

        try: f1("0", "0")
        except TypeError:
            t1 = f1
            f1 = lambda x,y: t1(y)
        except: pass

        values = {str(i): {"r0": x,"r1": x}
            for i,x in enumerate(from_a + ["null"] + from_b + ["null"])}
        pointers = {"0": {"r2": "arr1"},
            str(len(from_a)+1) : {"r2": "arr2"}}
        memory = (pointers, values)

        # Advances pointers along memory, performing the
        #   operation on all combinations of specified inputs.
        #
        # for x in from_a:
        #     for y in from_b:
        #         x (op) y
        #
        # r0, r1: argument
        # r2    : opcode, pointer
        program = """
        start:  mov r2 arr1
                drf r2
                mov r2 ptr1
                ref r2
                mov r2 arr2
                drf r2
                mov r2 ptr2
                ref r2

        loop:   mov r2 ptr2
                drf r2
                rem r1
                nxt
                ref r2
                cmp r1 null
                jie break

                mov r2 ptr1
                drf r2
                rem r0
                mov r2 %s

                jmp loop

        break:  mov r2 ptr1
                drf r2
                nxt
                ref r2
                rem r0
                cmp r0 null
                jie end

                mov r2 arr2
                drf r2
                mov r2 ptr2
                ref r2
                jmp loop

        end:    exit
        """ % opcode
        trace = [
            {},
            {"r2": "arr1" },
            {"r2": "arr1" },
            {"r2": "ptr1" },
            {"r2": "ptr1" },
            {"r2": "arr2" },
            {"r2": "arr2" },
            {"r2": "ptr2" },
            {"r2": "ptr2" },
        ]

        for i,x in enumerate(from_a):
            for y in from_b:
                try: v0,v1 = f0(x,y), f1(x,y)
                except: v0,v1 = 'null','null'

                # Loop iteration without break
                trace += [
                    {"r2" : "ptr2"},                       # mov
                    {},                                    # drf
                    {"r1": y },                            # rem
                    {},                                    # nxt
                    {},                                    # ref
                    {"co": "false"},                       # cmp
                    {},                                    # jie

                    {"r2" : "ptr1"},                       # mov
                    {},                                    # drf
                    {"r0": x , "r1": y },                  # rem
                    {"r0": x , "r1": y  ,"r2": opcode },   # mov

                    {"r0": v0, "r1": v1 ,"r2": "null" },   # jmp
                ]

            # Last loop iteration with break, post-loop code
            next_op = ("null" if i == len(from_a)-1 else from_a[i+1])
            trace += [
                {"r2" : "ptr2"},                           # mov
                {},                                        # drf
                {"r1": "null" },                           # rem
                {},                                        # nxt
                {},                                        # ref
                {"co": "true"},                            # cmp
                {},                                        # jie

                {"r2" : "ptr1"},                           # mov
                {},                                        # drf
                {},                                        # nxt
                {},                                        # ref
                {"r0": next_op},                           # rem
                {"cmp": "true"},                           # cmp
                {},                                        # jie

                {"r2": "arr2"},                            # mov
                {},                                        # drf
                {"r2": "ptr2"},                            # mov
                {},                                        # ref
                {},                                        # jmp
            ]
        trace.append({}) # exit

        self._test({"test":program}, ["test"], [trace], memory = memory,
            tokens = ["arr1", "arr2", "ptr1", "ptr2"] + self.all_tokens,
            num_registers=3, verbose=0)


    # @ut.skip("")
    def test_arith(self):
        for op in "+-*/":
            self._test_op(op, self.arith_opdef,
                sample(self.in_range, 3), sample(self.in_range, 3))

    # @ut.skip("")
    def test_unary(self):
        for op in ["++", "--"]:
            self._test_op(op, self.unary_opdef, ["0"], self.in_range)

    # @ut.skip("")
    def test_comp(self):
        for op in ["<", ">", "<=", ">="]:
            self._test_op(op, self.comp_opdef,
                sample(self.in_range, 3), sample(self.in_range, 3))


class SyngenNVMStreamTestCase(ut.TestCase):
    numerals = [str(x) for x in range(0,10)]
    all_tokens = numerals + ["read", "write", "null"]

    def _make_syngen_nvm(self, vm):
        return SyngenNVM(vm.net)

    def _make_syngen_env(self, vm):
        syn_env = SyngenEnvironment()

        # Stream in a null terminated random sequence of numerals
        # Validate when network streams them back out
        data = list(choice(self.numerals) for _ in range(12)) + ["null"]
        read_stream = iter(data)
        write_stream = iter(data)

        def producer():
            if random() < 0.01:
                sym = next(read_stream)
                #print("Produced %s" % sym)
                return True, sym
            else:
                return False, None

        def consumer(output):
            if random() < 0.01:
                #print("Consumed %s" % output)
                if output != next(write_stream):
                    print("Stream mismatch!")
                    interrupt_engine()
                return True
            else:
                return False

        syn_env.add_streams(vm.net, "r0", "r1", producer, consumer)

        return syn_env

    def _test(self, programs, names, traces,
            memory=None, tokens=[], num_registers=1, verbose=0):
        self.assertTrue(test_syngen(
            self, programs, names, traces,
            memory, tokens, num_registers, verbose))

    def _make_vm(self, num_registers, tokens):
        orthogonal = True
        layer_shape = (16,16) if orthogonal else (32,32)
        pad = 0.0001
        activator, learning_rule = tanh_activator, rehebbian
        register_names = ["r%d"%r for r in range(num_registers)]

        return NVM(layer_shape,
            pad, activator, learning_rule, register_names,
            shapes={}, tokens=tokens, orthogonal=orthogonal)

    # @ut.skip("")
    def test_stream(self):

        values = {}
        pointers = {"0": {"r0": "ptr"}}
        memory = (pointers, values)

        # Stream in null terminated data and write to memory
        # Then, stream them back out in order
        program = """
        start:  mov r0 ptr
                drf r0

        input:  mov r0 read

        wait:   cmp r0 read
                jie wait

                mem r1
                nxt

                cmp r1 null
                jie output
                jmp input

        output: mov r0 ptr
                drf r0

        loop:   rem r1
                mov r0 write
                nxt

        wait2:  cmp r0 write
                jie wait2

                cmp r1 null
                jie end
                jmp loop

        end:    exit
        """
        trace = [
            {},
        ]

        self._test({"test":program}, ["test"], [trace], memory=memory,
            tokens = self.all_tokens + ["ptr"],
            num_registers=2, verbose=0)




if __name__ == "__main__":
    test_suite = ut.TestLoader().loadTestsFromTestCase(SyngenNVMTestCase)
    ut.TextTestRunner(verbosity=2).run(test_suite)

    test_suite = ut.TestLoader().loadTestsFromTestCase(SyngenNVMArithTestCase)
    ut.TextTestRunner(verbosity=2).run(test_suite)

    test_suite = ut.TestLoader().loadTestsFromTestCase(SyngenNVMStreamTestCase)
    ut.TextTestRunner(verbosity=2).run(test_suite)
