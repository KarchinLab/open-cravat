'''
Interval Tree data structure for indexing a set of 
integer intervals of the form [start, end).

http://en.wikipedia.org/wiki/Interval_tree

Copyright 2013, Konstantin Tretyakov.
http://kt.era.ee/

Licensed under MIT license.
'''


class IntervalTree:
    '''
    Interval Tree data structure for indexing a set of 
    integer intervals of the form [start, end). 
    
    See: http://en.wikipedia.org/wiki/Interval_tree

    The tree assumes it is covered in intervals reasonably uniformly (reasonable assumption for our liftOver purposes),
    and always picks its center as the middle point between the prespecified "min" and "max" values. 
    No removal operation is implemented.
    
    >>> t = IntervalTree(0, 100)
    >>> t.query(2)
    []
    >>> t.add_interval(10, 25)
    >>> t.add_interval(15, 27)
    >>> t.sort()
    >>> t.query(10)
    [(10, 25, None)]
    >>> t.query(24)
    [(10, 25, None), (15, 27, None)]
    >>> t.query(25)
    [(15, 27, None)]
    >>> t.query(27)
    []
    '''
    __slots__ = ['min', 'max', 'center', 'single_interval', 'left_subtree', 'right_subtree', 
                 'mid_sorted_by_start', 'mid_sorted_by_end']

    def __init__(self, min, max):
        '''
        Creates a tree node for keeping intervals somewhere in the range [min...max).
        '''
        self.min = int(min)
        self.max = int(max)
        assert self.min < self.max
        self.center = (min + max)/2
        self.single_interval = None # We take special care of trees which only contain a single interval
        self.left_subtree = None  # Intervals which are all strictly to the left of center.
        self.right_subtree = None # Intervals which are all strictly to the right of center.
        self.mid_sorted_by_start = []  # Intervals which contain center, sorted by start position
        self.mid_sorted_by_end = []    # Same intervals, sorted by end position.
    
    def add_interval(self, start, end, data=None):
        '''
        Inserts an interval to the tree. 
        Note that when inserting we do not maintain appropriate sorting of the "mid" data structure.
        This should be done after all intervals are inserted.
        '''
        # Ignore intervals of 0 or negative length
        if (end - start) <= 0:
            return
        if self.single_interval is None:
            # This is an empty tree and we are adding the first interval. Just record it in a field.
            self.single_interval = (start, end, data)
        elif self.single_interval == 0:
            # This is a usual tree, use standard addition method
            self._add_interval(start, end, data)
        else:
            # This is a tree with a single interval. Convert to a usual tree.
            self._add_interval(*self.single_interval)
            self.single_interval = 0
            self._add_interval(start, end, data)
            
    def _add_interval(self, start, end, data=None):
        if end <= self.center:
            # Insert into left subtree
            if self.left_subtree is None:
                self.left_subtree = IntervalTree(self.min, self.center)
            self.left_subtree.add_interval(start, end, data)
        elif start > self.center:
            if self.right_subtree is None:
                self.right_subtree = IntervalTree(self.center, self.max)
            self.right_subtree.add_interval(start, end, data)
        else:
            self.mid_sorted_by_start.append((start, end, data))
            self.mid_sorted_by_end.append((start, end, data))
    
    def sort(self):
        '''
        Must be invoked after all intevals have been added to sort mid_** arrays.
        '''
        if self.single_interval is None or self.single_interval != 0:
            return # Nothing to do for empty and leaf trees.
        self.mid_sorted_by_start.sort(key = lambda x: x[0])
        self.mid_sorted_by_end.sort(key = lambda x: x[1], reverse=True)
        if self.left_subtree is not None:
            self.left_subtree.sort()
        if self.right_subtree is not None:
            self.right_subtree.sort()
    
    def query(self, x):
        '''
        Returns all intervals in the tree, which overlap given point, i.e. all (start, end, data) records, for which (start <= x < end).
        '''
        result = []
        self._query(x, result)
        return result
    
    def _query(self, x, result):
        '''
        Same as self.query, but uses a provided list to accumulate results into.
        '''
        if self.single_interval is None: # Empty
            return
        elif self.single_interval != 0:  # Single interval, just check whether x is in it
            if self.single_interval[0] <= x < self.single_interval[1]:
                result.append(self.single_interval)
        elif x < self.center:            # Normal tree, query point to the left of center
            if self.left_subtree is not None:
                self.left_subtree._query(x, result)
            for int in self.mid_sorted_by_start:
                if int[0] <= x:
                    result.append(int)
                else:
                    break
        else:  # Normal tree, query point to the right of center
            for int in self.mid_sorted_by_end:
                if int[1] > x:
                    result.append(int)
                else:
                    break
            if self.right_subtree is not None:
                self.right_subtree._query(x, result)

    def __len__(self):
        '''
        The number of intervals maintained in the tree.
        Note that adding zero- or negative-size intervals does not affect its size (they are not registered).
        
        >>> t = IntervalTree(0, 100)
        >>> t.add_interval(1, 10)
        >>> t.add_interval(20, 30)
        >>> t.add_interval(20, 20)
        >>> t.add_interval(20, 19)
        >>> len(t)
        2
        '''
        
        if self.single_interval is None:
            return 0
        elif self.single_interval != 0:
            return 1
        else:
            size = len(self.mid_sorted_by_start)
            if self.left_subtree is not None:
                size += len(self.left_subtree)
            if self.right_subtree is not None:
                size += len(self.right_subtree)
            return size
            
    def __iter__(self):
        if self.single_interval is None:
            return
        elif self.single_interval != 0:
            yield self.single_interval
        else:
            if self.left_subtree is not None:
                for s in self.left_subtree:
                    yield s
            for s in self.mid_sorted_by_start:
                yield s
            if self.right_subtree is not None:
                for s in self.right_subtree:
                    yield s

