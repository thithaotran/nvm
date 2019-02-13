import sys
sys.path.append('../nvm')

from sequencer import Sequencer
from syngen_nvm import *

import numpy as np
from itertools import product

arith_ops = {
    "+" : (lambda x,y:str( (int(x) + int(y)) / 10 ),
           lambda x,y:str( (int(x) + int(y)) % 10 )),
    "-" : (lambda x,y:str( (int(x) - int(y)) / 10 ),
           lambda x,y:str( (int(x) - int(y)) % 10 )),
    "*" : (lambda x,y:str( (int(x) * int(y)) / 10 ),
           lambda x,y:str( (int(x) * int(y)) % 10 )),
    "/" : (lambda x,y:str( (int(x) % int(y)) ),
           lambda x,y:str( (int(x) / int(y)) )),
}

unary_ops = {
    "++" : (lambda x:str( (int(x)+1) / 10 ),
            lambda x:str( (int(x)+1) % 10 )),
    "--" : (lambda x:str( (int(x)-1) / 10 ),
            lambda x:str( (int(x)-1) % 10 )),
}

comp_ops = {
    "<"  : (lambda x,y:str( int(x) <  int(y) ).lower(), ),
    ">"  : (lambda x,y:str( int(x) >  int(y) ).lower(), ),
    "<=" : (lambda x,y:str( int(x) <= int(y) ).lower(), ),
    ">=" : (lambda x,y:str( int(x) >= int(y) ).lower(), ),
}


class OpDef:
    def __init__(self, op_name, operations, in_ops, out_ops):
        self.op_name = op_name
        self.operations = dict(operations)
        self.in_ops = list(in_ops)
        self.out_ops = list(out_ops)
        if 'null' not in out_ops:
            self.out_ops.append('null')
        self.tokens = list(set(
            self.operations.keys() + self.in_ops + self.out_ops))

def make_arith_opdef(in_range=range(0,10),out_range=range(-9,10)):
    return OpDef("arith", arith_ops,
        (str(x) for x in in_range),
        (str(x) for x in out_range))

def make_unary_opdef(in_range=range(0,10),out_range=range(-9,10)):
    return OpDef("unary", unary_ops,
        (str(x) for x in in_range),
        (str(x) for x in out_range))

def make_comp_opdef(in_range=range(0,10)):
    return OpDef("comp", comp_ops,
        (str(x) for x in in_range),
        ("true", "false"))

class OpNet:
    def __init__(self, nvmnet, opdef, in_regs, out_regs, op_reg):
        self.opdef = opdef
        self.op_name = opdef.op_name
        self.operations = dict(opdef.operations)
        self.in_ops = list(opdef.in_ops)
        self.out_ops = list(opdef.out_ops)
        self.tokens = list(opdef.tokens)

        self.input_registers = in_regs
        self.output_registers = out_regs
        self.op_register = op_reg

        self.gate_name = "%s_gate" % self.op_name
        self.input_name = "%s_input" % self.op_name
        self.hidden_name = "%s_hidden" % self.op_name
        self.output_name = "%s_output" % self.op_name

        self.gate_size = len(self.operations)
        self.input_size = len(self.in_ops) * len(self.input_registers)
        self.hidden_size = len(self.in_ops) ** len(self.input_registers)
        self.output_size = len(self.out_ops) * len(self.output_registers)

        op_reg = nvmnet.layers[self.op_register]
        gate_bias = op_reg.activator.on * -(op_reg.size - 1)

        # Gate layer (detects operator)
        gate_layer = {
            "name" : self.gate_name,
            "neural model" : "binary threshold",
            "rows" : 1,
            "columns" : self.gate_size,
            "init config": {
                "type": "flat",
                "value": gate_bias
            }
        }
        # Input layer
        input_layer = {
            "name" : self.input_name,
            "neural model" : "nvm_heaviside",
            "rows" : 1,
            "columns" : self.input_size,
        }
        # Hidden layer
        # Bias is set according to the number of input registers
        hidden_layer = {
            "name" : self.hidden_name,
            "neural model" : "nvm_heaviside",
            "rows" : 1,
            "columns" : self.hidden_size,
            "init config": {
                "type": "flat",
                "value": -len(self.input_registers)+0.5
            }
        }
        # Output layer
        output_layer = {
            "name" : self.output_name,
            "neural model" : "nvm_heaviside",
            "rows" : 1,
            "columns" : self.output_size,
        }
        self.structure = {
            "name" : self.op_name,
            "type" : "sequential",
            "layers": [gate_layer, input_layer, hidden_layer, output_layer]
        }

        def build_gate(to_name, indices=(0, self.gate_size), suffix=""):
            return {
                "name" : get_conn_name(to_name, self.gate_name, suffix),
                "from layer" : self.gate_name,
                "to layer" : to_name,
                "type" : "subset",
                "opcode" : "add",
                "subset config" : {
                    "from row end" : 1,
                    "from column start" : indices[0],
                    "from column end" : indices[1],
                    "to row end" : 1,
                    "to column end" : 1,
                },
                "plastic" : False,
                "gate" : True,
            }

        def build_fc(to_name, from_name, gated=True, suffix=""):
            return {
                "name" : get_conn_name(to_name, from_name, suffix),
                "from layer" : from_name,
                "to layer" : to_name,
                "type" : "fully connected",
                "opcode" : "add",
                "plastic" : False,
                "gated" : gated,
            }

        def build_subset(to_name, from_name, sub_conf, gated=True, suffix=""):
            return {
                "name" : get_conn_name(to_name, from_name, suffix),
                "from layer" : from_name,
                "to layer" : to_name,
                "type" : "subset",
                "opcode" : "add",
                "subset config" : sub_conf,
                "plastic" : False,
                "gated" : gated,
            }


        self.connections = []

        # Operation gate activation (detect operation)
        self.connections.append(
            build_fc(self.gate_name, self.op_register, gated=False))

        # Operands to input
        self.connections.append(
            build_gate(self.input_name));

        # Input bias (for different sized x/y layers)
        self.connections.append(
            build_fc(self.input_name, 'bias', gated=True))

        for index,from_name in enumerate(self.input_registers):
            self.connections.append(build_subset(self.input_name, from_name, {
                "from row end" : nvmnet.layers[from_name].shape[0],
                "from column end" : nvmnet.layers[from_name].shape[1],
                "to row end" : 1,
                "to column start" : index*len(self.in_ops),
                "to column end" : (index+1)*len(self.in_ops),
            }, gated=True))

        # Input to hidden
        self.connections.append(
            build_gate(self.hidden_name));
        self.connections.append(
            build_fc(self.hidden_name, self.input_name, gated=True))

        # Hidden to output
        for index,op in enumerate(self.operations):
            self.connections.append(
                build_gate(self.output_name, (index, index+1), op));
            self.connections.append(
                build_fc(self.output_name, self.hidden_name, gated=True, suffix=op))

        # Output bias (for 'null')
        self.connections.append(
            build_fc(self.output_name, 'bias', gated=False))

        # Output to operands
        for index,to_name in enumerate(self.output_registers):
            self.connections.append(build_gate(to_name, suffix=self.op_name));

            # Output
            self.connections.append(build_subset(to_name, self.output_name, {
                "from row end" : 1,
                "from column start" : index*len(self.out_ops),
                "from column end" : (index+1)*len(self.out_ops),
                "to row end" : nvmnet.layers[from_name].shape[0],
                "to column end" : nvmnet.layers[from_name].shape[1],
            }, gated=True))

            # Squash
            self.connections.append({
                "name" : get_conn_name(to_name, to_name, "%s-squash" % self.op_name),
                "from layer" : to_name,
                "to layer" : to_name,
                "type" : "one to one",
                "opcode" : "add",
                "weight config" : {
                    "type" : "flat",
                    "weight" : -nvmnet.w_gain[to_name],
                },
                "plastic" : False,
                "gated" : True,
            })

        # Operation squash
        self.connections.append(
            build_fc(self.op_register, self.gate_name, gated=False))


    def initialize(self, syngen_net, nvmnet):

        # Detector weights
        # Map each operator to a gate node
        op_layer = nvmnet.layers[self.op_register]

        w = np.zeros((0,op_layer.size))
        for op in self.operations.keys():
            op_pattern = np.sign(
                op_layer.coder.encode(op).reshape((1,op_layer.size)))
            w = np.append(w, op_pattern, axis=0)

        syngen_net.net.get_weight_matrix(
            get_conn_name(self.gate_name, self.op_register)).copy_from(w.flat)

        # Input bias
        # For mutually exlusive operand detection
        w = np.zeros((0,1))
        for name in self.input_registers:
            reg = nvmnet.layers[name]
            bias = reg.activator.on * -(reg.size - 1)
            w = np.append(w, bias * np.ones((len(self.in_ops),1)), axis=0)
        syngen_net.net.get_weight_matrix(
            get_conn_name(self.input_name, 'bias')).copy_from(w.flat)

        # Operands to input
        # Map each operand to an input node
        for from_name in self.input_registers:
            from_layer = nvmnet.layers[from_name]
            w = np.zeros((0,from_layer.size))

            for operand in self.in_ops:
                op_pattern = np.sign(
                    from_layer.coder.encode(
                        operand).reshape((1,from_layer.size)))
                w = np.append(w, op_pattern, axis=0)

            syngen_net.net.get_weight_matrix(
                get_conn_name(self.input_name, from_name)).copy_from(w.flat)

        # Input to hidden
        # Each hidden node is a unique combination of operands
        w = np.zeros((self.hidden_size, self.input_size))
        combos = product(range(len(self.in_ops)), repeat=len(self.input_registers))
        for hid_index,elems in enumerate(combos):
            for i,e in enumerate(elems):
                w[hid_index,i*len(self.in_ops)+e] = 1

        syngen_net.net.get_weight_matrix(
            get_conn_name(self.hidden_name, self.input_name)).copy_from(w.flat)

        # Hidden to output
        # Each operation maps operand combos to outputs
        # Any exception yields a 'null' output
        nulls = [self.out_ops.index('null') + i*len(self.out_ops)
            for i in range(len(self.output_registers))]
        for op,fs in self.operations.iteritems():
            w = np.zeros((self.output_size, self.hidden_size))

            # Create the map
            # 'null' is the default output if no hidden node is active
            # For this reason, weights to 'null' are 2, not 1
            # They will be decremented to 1, and 'null' will be biased
            combos = product(self.in_ops, repeat=len(self.input_registers))
            for hid_index,elems in enumerate(combos):
                try:
                    outputs = tuple(self.out_ops.index(f(*elems)) for f in fs)
                except:
                    outputs = tuple(self.out_ops.index('null') for f in fs)

                for i,o in enumerate(outputs):
                    w[o+(i*len(self.out_ops)),hid_index] = 1

            # Decrement all weights into 'null' outputs
            for null_index in nulls:
                w[null_index,:] -= 1

            syngen_net.net.get_weight_matrix(get_conn_name(
                self.output_name, self.hidden_name, op)).copy_from(w.flat)

        # Output bias
        # For 'null'
        w = np.zeros((self.output_size, 1))
        for null_index in nulls:
            w[null_index] = 1
        syngen_net.net.get_weight_matrix(
            get_conn_name(self.output_name, 'bias')).copy_from(w.flat)

        # Output to operands
        # Each output node is mapped back to a distributed representation
        for index,to_name in enumerate(self.output_registers):
            to_layer = nvmnet.layers[to_name]
            w = np.zeros((to_layer.size,0))

            for operand in self.out_ops:
                op_pattern = to_layer.activator.g(
                    to_layer.coder.encode(operand).reshape((to_layer.size,1)))
                w = np.append(w, op_pattern, axis=1)

            syngen_net.net.get_weight_matrix(
                get_conn_name(to_name, self.output_name)).copy_from(w.flat)

        # Operation squash
        # Pushes the operand layer to 'null' to avoid repeated operations
        op_layer = nvmnet.layers[self.op_register]
        null_pattern = op_layer.activator.g(
            op_layer.coder.encode('null').reshape((op_layer.size,1)))

        w = np.zeros((op_layer.size,0))
        for op in self.operations.keys():
            op_pattern = nvmnet.w_gain[self.op_register] * \
                op_layer.coder.encode(op).reshape((op_layer.size,1))
            w = np.append(w, null_pattern - op_pattern, axis=1)

        syngen_net.net.get_weight_matrix(
            get_conn_name(self.op_register, self.gate_name)).copy_from(w.flat)
