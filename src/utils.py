from datetime import datetime


class Intervals:
    def __init__(self, interval_list):
        self.interval_list = []
        self.interval_list = self.union(interval_list)
    
    def union(self, interval_list):
        interval_list += self.interval_list
        if len(interval_list) == 0:
            return []
        interval_list.sort(key=lambda x: x[0])
        stack = [interval_list[0]]
        
        # insert first interval into stack
        for i in interval_list[1:]:
            # Check for overlapping interval,
            # if interval overlap
            if stack[-1][0] <= i[0] <= stack[-1][-1]:
                stack[-1][-1] = max(stack[-1][-1], i[-1])
            else:
                stack.append(i)
        stack.sort(key=lambda x: x[0])
        return stack

    def intersect(self, interval_list) -> list:
        # Loop through all intervals unless one
        # of the interval gets exhausted
        i = j = 0
        stack = []
        while i < len(self.interval_list) and j < len(interval_list):
            
            # Left bound for intersecting segment
            l = max(self.interval_list[i][0], interval_list[j][0])
            
            # Right bound for intersecting segment
            r = min(self.interval_list[i][1], interval_list[j][1])
            
            # If segment is valid
            if l <= r: 
                stack.append([l, r])
    
            # If i-th interval's right bound is
            # smaller increment i else increment j
            if self.interval_list[i][1] < interval_list[j][1]:
                i += 1
            else:
                j += 1
        
        stack.sort(key=lambda x: x[0])
        return stack
    
            