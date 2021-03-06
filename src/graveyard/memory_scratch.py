import numpy as np
import matplotlib.pyplot as plt

np.set_printoptions(linewidth=1000)

class KVNet:
    """
    Feed-forward net for neural key-value memory
    """
    def __init__(self, N, f, df, af):
        # N[k]: size of k^th layer (len L+1)
        # f[k]: activation function of k^th layer (len L)
        # df[k]: derivative of f[k] (len L)
        # af[k]: inverse of f[k] (len L)
        self.L = len(N)-1 #
        self.N = N
        self.f = f
        self.df = df
        self.af = af
        # self.W = [np.random.randn(N[k+1],N[k])/(N[k+1]*N[k]) for k in range(self.L)]
        self.W = [np.eye(N[k+1],N[k]) for k in range(self.L)]
        self.O = [np.zeros((N[k+1],N[k])) for k in range(self.L)]
    def forward_pass(self, x_0):
        # x_0: input layer activity pattern
        x = {0: x_0}
        for k in range(self.L):
            x[k+1] = self.f[k]((self.W[k]+self.O[k]).dot(x[k]))
        return x
    def backward_pass(self, x, d):
        # x[k]: k^th layer activity pattern from forward pass
        # d: target pattern for L^th layer
        k = self.L
        e = (x[k] - d)
        y = {}
        for k in range(self.L,0,-1):
            y[k] = self.df[k-1]((self.W[k-1]+self.O[k-1]).dot(x[k-1])) * e
            e = (self.W[k-1]+self.O[k-1]).T.dot(y[k])
        return y
    def error_gradient(self, x, y):
        # x,y from forward/backward pass
        # returns error gradient wrt omega
        return [y[k+1] * x[k].T for k in range(self.L)]
    def gradient_descent(self, x_0, d, eta=0.01, num_epochs=10000, verbose=2):
        for k in range(L): self.O[k] *= 0.
        for epoch in range(num_epochs):
            x = self.forward_pass(x_0)
            y = self.backward_pass(x, d)
            if epoch % int(num_epochs/10) == 0:
                E = 0.5*((x[self.L]-d)**2).sum()
                if verbose > 0: print('%d: %f'%(epoch,E))
                if verbose > 1:
                    print(x[self.L].T)
                    print(d.T)
            G = self.error_gradient(x, y)
            for k in range(self.L):
                kvn.O[k] += - eta * G[k]
        # Persist weight changes
        for k in range(self.L):
            kvn.W[k] += kvn.O[k]
            kvn.O[k] *= 0
    def memorize(self, x_0, d, eta=0.01, num_epochs=5000, dot_term=0.999, verbose=1):
        x = self.forward_pass(x_0)
        for k in range(L-1): self.O[k] *= 0.
        self.O[L-1]  = (self.af[L-1](d) - self.W[L-1].dot(x[L-1])) * x[L-1].T / (x[L-1].T.dot(x[L-1]))
        learning_curve = []
        epoch = 0
        while True:
            # progress
            x = self.forward_pass(x_0)
            y = self.backward_pass(x,d)
            g = self.error_gradient(x,y)
            E = 0.5*((x[self.L]-d)**2).sum()
            O = sum([(self.O[k]**2).sum() for k in range(self.L)])
            G = sum([(g[k]**2).sum() for k in range(self.L)])
            GO = sum([(g[k]*self.O[k]).sum() for k in range(self.L)])
            if epoch % int(np.ceil(num_epochs/10. + 1)) == 0:
                # P = sum([(g[k]*self.O[k]).sum() for k in range(self.L)])
                if verbose > 0:
                    term = GO**2/(G*O) if G*O > 0 else 0
                    print('%d: E=%f,O=%f,term=%f'%(epoch,E,O,term))
                if verbose > 1:
                    print(x[self.L].T)
                    print(d.T)
            learning_curve.append((E,O,G,GO))
            # termination
            if epoch == num_epochs: break
            if G*O > 0 and GO**2/(G*O) > dot_term: break
            # predictor
            H = GO/G if G > 0 else 0
            for k in range(self.L):
                self.O[k] *= 1 - eta
                self.O[k] += eta * g[k] * H
            # corrector
            x = self.forward_pass(x_0)
            y = self.backward_pass(x, d)
            g = self.error_gradient(x, y)
            for k in range(self.L):
                self.O[k] += - eta * g[k]
            epoch += 1
        # Persist weight changes
        for k in range(self.L):
            kvn.W[k] += kvn.O[k]
            kvn.O[k] *= 0
        return learning_curve

# Activation functions
def slog_f(x): return (-1.)**(x < 0)*np.log(np.fabs(x)+1.)
def slog_df(x): return 1./(np.fabs(x)+1.)
def slog_af(y): return (-1.)**(y < 0)*(np.exp(np.fabs(y))-1.)
def tanh_df(x): return 1. - np.tanh(x)**2.

def int_to_pattern(N, i):
    return (-1)**(1 & (i >> np.arange(N)[:,np.newaxis]))
def pattern_to_int(N, p):
    if np.isnan(p).any(): return -1
    else: return (2**np.arange(N)).dot(p < 1).flat[0]
def hash_pattern(p):
    return tuple(p.flatten())
def unhash_pattern(p):
    return np.array((p,)).T

class MockMemoryNet:
    def __init__(self, N, noise=0):
        self.N = N
        self.noise = noise
        self.key_value_map = {} # key-value "network"
    def _noise(self,p):
        return p * (-1)**(np.random.rand(self.N,1) < self.noise)
    def read(self,k):
        if hash_pattern(k) in self.key_value_map:
            return self.key_value_map[hash_pattern(k)]
        else:
            return np.sign(np.random.randn(self.N,1))
        # k = hash_pattern(self._noise(k))
        # if k in self.key_value_map:
        #     return self._noise(self.key_value_map[k])
        # else:
        #     return np.sign(np.random.randn(self.N,1))
    def write(self,k,v):
        self.key_value_map[hash_pattern(self._noise(k))] = self._noise(v)
    def next(self, k):
        return self._noise(int_to_pattern(self.N, pattern_to_int(self.N,k)+1))
    def first(self):
        return self._noise(int_to_pattern(self.N, 0))
    def passive_tick(self):
        pass
    # def new(self):
    #     return int_to_pattern(self.N, len(self.key_value_map))

class MemoryNetTrace:
    """
    Wrap network to record key sequence and ideal key value mapping
    """
    def __init__(self, net):
        self.net = net
        self.key_sequence = {} # k -> next k
        self.key_value_map = {} # k -> value
    def read(self, k):
        return self.net.read(k)
    def write(self, k, v):
        self.net.write(k,v)
        self.key_value_map[hash_pattern(k)] = v
        if len(self.key_value_map) >= 2**self.net.N:
            print('Warning: Address capacity reached!')
    def next(self, k):
        k_next = self.net.next(k)
        self.key_sequence[hash_pattern(k)] = k_next
        return k_next
    def first(self):
        return self.net.first()
    def memory_string(self, to_int=True):
        def _val(k):
            if hash_pattern(k) in self.key_value_map:
                return self.key_value_map[hash_pattern(k)]
            else: return np.nan*np.ones((self.net.N,1))
        k = self.first()
        keys = [k]
        values = [_val(k)]
        while hash_pattern(k) in self.key_sequence:
            k = self.key_sequence[hash_pattern(k)]
            keys.append(k)
            values.append(_val(k))
        if to_int:
            string = 'keys/values:\n'
            string += str(np.array([
                [pattern_to_int(self.net.N,k) for k in keys],
                [pattern_to_int(self.net.N,v) for v in values]]))
        else:
            string = 'keys:\n'
            string += str(np.concatenate(keys,axis=1))
            string += '\nvalues:\n'
            string += str(np.concatenate(values,axis=1))
        return string
    def accuracy(self):
        keys = self.key_sequence.keys()
        test_sequence = np.concatenate([self.key_sequence[k] for k in keys],axis=1)
        net_sequence = np.concatenate([self.net.next(unhash_pattern(k)) for k in keys],axis=1)
        keys = self.key_value_map.keys()
        test_map = np.concatenate([self.key_value_map[k] for k in keys],axis=1)
        net_map = np.concatenate([self.net.read(unhash_pattern(k)) for k in keys],axis=1)
        acc = lambda x: 1.0*x.sum()/x.size
        sequence_accuracy = acc(test_sequence==net_sequence)
        map_accuracy = acc(test_map==net_map)
        return sequence_accuracy, map_accuracy

def linked_list_trial_data(N, num_lists, max_prepends, max_passive_ticks):
    """
    Generate random trial data for different nets with the same layer size N    
    """
    num_prepends = []
    num_cells = 1
    tail_index = []
    patterns = []
    num_passive_ticks = []
    for n in range(num_lists):
        num_prepends.append(np.random.randint(1,max_prepends+1))
        tail_index.append(np.random.randint(num_cells))
        # construct new list
        for p in range(num_prepends[-1]):
            num_cells += 1
            patterns.append(np.sign(np.random.randn(N,1)))
        num_passive_ticks.append(np.random.randint(max_passive_ticks+1))
    return num_prepends, tail_index, patterns, num_passive_ticks

def linked_list_trial(mnt, num_prepends, tail_index, patterns, num_passive_ticks):
    """
    Test linked list construction and retrieval.
    mnt is a MemoryNetTrace wrapping the network being tested
    "NIL" terminal is mnt.first()
    "cons cells" are (car=v, cdr=k_next) pairs stored in consecutive memory locations
    Constructs multiple overlapping linked lists
    The n^th list is prepended to the tail_index[n]^th cell used so far
    New "cons cells" for n^th list are prepended num_prepends[n] times
    Cell contents are drawn from patterns in order
    After n^th list num_passive_ticks[n] time steps are allowed
    After all lists constructed, traverses and circularly rotates the last one
    For evaluation, return full sequence of next() outputs and full dictionary of write() inputs
    """
    k_first = mnt.first() # very first memory address
    k_last = k_first # last key written to
    cell_keys = [k_first] # "NIL" "cell"
    patterns = list(patterns) # copy before popping
    for n in range(len(num_prepends)):
        # initialize tail for new list 
        k_tail = cell_keys[tail_index[n]]
        # construct new list
        for p in range(num_prepends[n]):
            # get memory addresses for cons cell
            k_car = mnt.next(k_last)
            k_cdr = mnt.next(k_car)
            k_last = k_cdr # update last address used
            cell_keys.append(k_car) # update cells used so far
            # store pattern and prepend to tail
            pattern = patterns.pop(0)
            mnt.write(k_car, pattern)
            mnt.write(k_cdr, k_tail)
            k_tail = k_car # update tail
        # run network in passive mode
        for _ in range(num_passive_ticks[n]):
            mnt.passive_tick()
    # Traverse last list
    k_head = k_tail
    last_list = [[],[]]
    k_car = k_head
    while not (k_car == k_first).all():
        last_list[0].append(k_car)
        last_list[1].append(mnt.read(k_car))
        k_car = mnt.read(mnt.next(k_car))
    # Circularly rotate the last list
    k_car = mnt.read(mnt.next(k_head))
    v_prev = mnt.read(k_head)
    while not (k_car == k_first).all():
        v_curr = mnt.read(k_car)
        mnt.write(k_car, v_prev)
        k_car = mnt.read(mnt.next(k_car))
        v_prev = v_curr
    mnt.write(k_head, v_prev)
    # traverse rotated list
    last_list_rotated = [[],[]]
    k_car = k_head
    while not (k_car == k_first).all():
        last_list_rotated[0].append(k_car)
        last_list_rotated[1].append(mnt.read(k_car))
        k_car = mnt.read(mnt.next(k_car))
    return last_list, last_list_rotated
    
if __name__=='__main__':

    while True:
        N = 8
        mmn = MockMemoryNet(N, noise=0.0005)
        mnt = MemoryNetTrace(mmn)
        
        trial_data = linked_list_trial_data(N, num_lists=4, max_prepends=8, max_passive_ticks=0)
        num_prepends, tail_index, patterns, num_passive_ticks = trial_data
        last_list, last_list_rotated = linked_list_trial(mnt, *trial_data)
        # last_list = np.concatenate([np.concatenate(last_list[0],axis=1),np.concatenate(last_list[1],axis=1)],axis=0)
        # last_list_rotated = np.concatenate([np.concatenate(last_list_rotated[0],axis=1),np.concatenate(last_list_rotated[1],axis=1)],axis=0)
        last_list_values = np.concatenate(last_list[1],axis=1)
        last_list_rotated_values = np.concatenate(last_list_rotated[1],axis=1)
        # print('list rotation:')
        # print(last_list)
        # print(last_list_rotated)
        # print(np.roll(last_list,1,axis=1)==last_list_rotated)
        print('tail_index',tail_index)
        print('prepends:',num_prepends)
        print('memory state:')
        print(mnt.memory_string())
        correct_shape = (last_list_values.shape==last_list_rotated_values.shape)
        correct_rotation = correct_shape and (np.roll(last_list_values,1,axis=1)==last_list_rotated_values).all()
        print('correct shape:',correct_shape)
        print('correct rotation:',correct_rotation)
        mnt_acc = mnt.accuracy()
        print('mnt acc:',mnt_acc)
        if mnt_acc[0]==1. and mnt_acc[1]==1. and not correct_rotation:
            print([pattern_to_int(mmn.N,last_list_values[:,[p]]) for p in range(last_list_values.shape[1])])
            print([pattern_to_int(mmn.N,last_list_rotated_values[:,[p]]) for p in range(last_list_rotated_values.shape[1])])
            break

    # print('num prep',num_prepends)
    # print('tail_index',tail_index)
    # print('num_passive_ticks',num_passive_ticks)
    # print('patterns:')
    # print(np.concatenate(patterns,axis=1))
    
    # # evaluate performance
    # print('next results:')
    # test_sequence = np.concatenate(key_sequence,axis=1)
    # net_sequence = np.concatenate([mmn.first()] + [mmn.next(k) for k in key_sequence[:-1]],axis=1)
    # print(test_sequence==net_sequence)
    
    # print('mapping results:')
    # test_values = np.concatenate([key_value_map[hash_pattern(k)] for k in key_sequence[1:]],axis=1)
    # net_values = np.concatenate([mmn.read(k) for k in key_sequence[1:]],axis=1)
    # print(test_values==net_values)

    # acc = lambda x: 1.0*x.sum()/x.size
    # print('sequence accuracy = %f'%acc(test_sequence==net_sequence))
    # print('value accuracy = %f'%acc(test_values==net_values))
    
    # print(key_sequence, key_value_map)
    # meaningful k,v pairs:

    # # storing/retrieving from an array
    # k_first = mmn.first()
    # k_curr = k_first
    # for i in range(7,-1,-1):
    #     mmn.write(k_curr, int_to_pattern(N,i))
    #     k_curr = mmn.next(k_curr)
    # k_curr = k_first
    # for k in range(8):
    #     print(k_curr.T, mmn.read(k_curr).T)
    #     k_curr = mmn.next(k_curr)

    # # constructing/storing/retrieving from a linked list
    # # linked list: stores v, k_next at adjacent memory locations
    # k_first = mmn.first()
    # k_last = k_first
    # k_tail = k_first
    # L = 5
    # # construct len-5 list
    # for i in range(5):
    #     k_car = mmn.next(k_last)
    #     k_cdr = mmn.next(k_car)
    #     k_last = k_cdr
    #     mmn.write(k_car, int_to_pattern(N,3*i))
    #     mmn.write(k_cdr, k_tail)
    #     k_tail = k_car
    # k_list_1 = k_tail
    # # traverse forward 2 elements
    # for i in range(2):
    #     k_tail = mmn.read(mmn.next(k_tail))
    # # branch off with len-3 list
    # for i in range(3):
    #     k_car = mmn.next(k_last)
    #     k_cdr = mmn.next(k_car)
    #     k_last = k_cdr
    #     mmn.write(k_car, int_to_pattern(N,5*i))
    #     mmn.write(k_cdr, k_tail)
    #     k_tail = k_car
    # k_list_2 = k_tail
    # # read back first list
    # print('list 1')
    # k_curr = k_list_1
    # k_car = k_curr
    # while not (k_curr == k_first).all():
    #     car, k_curr = mmn.read(k_car), mmn.read(mmn.next(k_car))
    #     print(k_car.T, car.T, k_curr.T)
    #     k_car = k_curr
    # # read back second list
    # print('list 2')
    # k_curr = k_list_2
    # k_car = k_curr
    # while not (k_curr == k_first).all():
    #     car, k_curr = mmn.read(k_car), mmn.read(mmn.next(k_car))
    #     print(k_car.T, car.T, k_curr.T)
    #     k_car = k_curr
            
    # constructing/storing/retrieving from a graph

def kvn_test():
    np.set_printoptions(linewidth=200)
    # Network size
    N = [4]*5
    L = len(N)-1
    M = 5 #sum(N) # num training examples
    keys = np.sign(np.random.randn(N[0],M))
    vals = 0.9*np.sign(np.random.randn(N[L],M)) #*(1./N[L])
    for num_epochs in [0, 10000]:
        for (f, df, af) in [
            # ([slog_f]*L, [slog_df]*L, [slog_af]*L),
            ([np.tanh]*L, [tanh_df]*L, [np.arctanh]*L)
        ]:
            kvn = KVNet(N, f, df, af)
            for m in range(M):            
                learning_curve = kvn.memorize(keys[:,[m]], vals[:,[m]],eta=0.001,num_epochs=num_epochs,verbose=1,dot_term=.99)
                E, O, G, GO = zip(*learning_curve)
                # # for k in range(L):
                # #     print(kvn.W[k])
                # # plt.ion()
                # plt.plot(E)
                # plt.plot(O)
                # plt.plot(G)
                # plt.legend(['Error','Omega norm','Gradient norm'])
                # plt.show()        
                outs = np.concatenate([kvn.forward_pass(keys[:,[_m]])[L] for _m in range(m+1)], axis=1)
                E = 0.5*((outs - vals[:,:m+1])**2).sum(axis=0)
                A = 1.0*(np.sign(outs) == np.sign(vals[:,:m+1])).sum(axis=0)/N[L]
                term = GO[-1]**2/(G[-1]*O[-1]) if G[-1]*O[-1] > 0 else 0
                print('%d: %d iters, O = %f, G = %f, term=%f, avg E = %f, avg A = %f'%(m,len(learning_curve), O[-1], G[-1], term, E.mean(),A.mean()))
                # print(E)
                print(A)
        # print(keys)
        # print(vals)
        # outs = np.concatenate([kvn.forward_pass(keys[:,[m]])[L] for m in range(M)], axis=1)
        # E = 0.5*((outs - vals)**2).sum(axis=0)
        # A = 1.0*(np.sign(outs) == np.sign(vals)).sum(axis=0)/N[L]
        # print(E)
        # print(A)
    
        # kvn.gradient_descent(x_0, d)
    
        # x_0, d = keys[:,[0]], vals[:,[0]]
        # learning_curve = kvn.memorize(x_0, d, eta=0.001,num_epochs=10000,verbose=1,dot_term=.99)
        # E, O, G, GO = zip(*learning_curve)
        # # plt.ion()
        # plt.plot(E)
        # plt.plot(O)
        # plt.plot(G)
        # plt.plot(np.array(GO)**2/(np.array(G)*np.array(O)))
        # plt.legend(['Error','Omega norm','Gradient norm','Term'])
        # plt.show()

def weight_update(W, G, X, Y):
    # learn X -> Y, each N x K
    # want
    #   np.tanh(W.dot(X)) = Y
    # or equivalently
    #   W.dot(X) = np.arctanh(Y)
    # competition of i and j at t measured by:
    #   C[i,j] = np.log(1+np.exp(-G[i,j])
    # where
    #   G[i,j] += (Y[i]*W[i,j]*X[j])
    # So, objective (obj), for each i separately:
    #   minimize ((dW[i,:]**2)*C[i,:]).sum()
    # subject to (sbt)
    #   (W+dW)[i,:].dot(X) - np.arctanh(Y[i,:]) = np.zeros((1,K))
    #   dW[i,:].dot(X) = np.arctanh(Y[i,:]) - W[i,:].dot(X)
    # Grads wrt to dW:
    #   obj: 2*(dW*C)[i,:]
    #   sbt: X.T
    # Lagrange says grad obj is lin comb of grad sbt:
    #   2*(dW*C)[i,:] = L.dot(X.T)
    # L is 1 x K lagrange multipliers.  Substitute out dW ito L in sbt:
    #   dW[i,:] = L.dot(X.T)/(2*C[i,:])
    #   (L.dot(X.T)/(2*C[i,:])).dot(X) = np.arctanh(Y[i,:]) - W[i,:].dot(X)
    #   L = mrdivide(np.arctanh(Y[i,:]) - W[i,:].dot(X), (X.T/(2*C[i,:])).dot(X))
    # Substitute back into obj:
    #   2*(dW*C)[i,:] = mrdivide(np.arctanh(Y[i,:]) - W[i,:].dot(X), (X.T/(2*C[i,:])).dot(X)).dot(X.T)
    #   dW[i,:] = mrdivide(np.arctanh(Y[i,:]) - W[i,:].dot(X), (X.T/(2*C[i,:])).dot(X)).dot(X.T)/(2*C[i,:])
    # If K == 1: (X.T/(2*C[i,:])).dot(X) is scalar, mrdivide is just scalar divide
    N = W.shape[0]
    T = X.shape[1]
    W = np.zeros((N,N,T))
    dW = np.zeros((N,N,T))
    G = np.zeros((N,N,T))
    for t in range(T):
        pass
