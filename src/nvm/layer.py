import numpy as np
from orthogonal_patterns import random_orthogonal_patterns
# import added for python3
from functools import reduce


class Layer:
    def __init__(self, name, shape, activator, coder):
        self.name = name
        self.shape = shape
        self.activator = activator
        self.coder = coder
        self.size = reduce(lambda x, y: x * y, shape)
    def encode_tokens(self, tokens, orthogonal=False):
        """
        Return patterns encoding a list of tokens
        """
        T = len(tokens)
        if orthogonal:
            on, off = self.activator.on, self.activator.off
            patterns = random_orthogonal_patterns(self.size, T)
            patterns = off + (on - off)*(patterns + 1.)/2.
            for t in range(T):
                self.coder.encode(tokens[t], patterns[:,[t]])
        else:
            patterns = [np.empty((self.size,0))] # in case of empty token list
            for t in range(T):
                patterns.append(self.coder.encode(tokens[t]))
            patterns = np.concatenate(patterns, axis=1)
        return patterns
    def all_tokens(self):
        return self.coder.encodings.keys()
