import json

class FilterColumn(object):

    test2sql = {
        'equals': '==',
        'lessThanEq': '<=',
        'lessThan': '<',
        'greaterThanEq': '>=',
        'greaterThan': '>',
        'hasData': '!= null',
        'noData': '== null',
        'stringContains': 'like',
        'stringStarts': 'like',
        'stringEnds': 'like',
        'between': 'between'
    }

    def __init__(self, d):
        self.column = d['column']
        self.test = d['test']
        self.value = d['value']
        self.negate = d.get('negate',False)
    
    def get_sql(self):
        s = self.column+' '+self.test2sql[self.test]
        if type(self.value) == 'str':
            if self.test == 'stringContains':
                sql_val = '"%{}%"'.format(self.value)
            elif self.test == 'stringStarts':
                sql_val = '"{}%"'.format(self.value)
            elif self.test == 'stringEnds':
                sql_val = '"%{}"'.format(self.value)
            else:
                sql_val = '"{}"'.format(self.value)
        elif self.value is None:
            sql_val = ''
        else:
            sql_val = str(self.value)
        if len(sql_val) > 0:
            s += ' '+sql_val
        if self.negate:
            s = 'not('+s+')'
        return s

class FilterGroup(object):
    def __init__(self, d):
        self.operator = d['operator']
        self.negate = d.get('negate',False)
        self.groups = [FilterGroup(x) for x in d.get('groups',[])]
        self.columns = [FilterColumn(x) for x in d['columns']]

    def get_sql(self):
        all_operands = self.groups + self.columns
        if len(all_operands) == 0:
            return ''
        s = '('
        sql_operator = ' '+self.operator+' '
        s += sql_operator.join([x.get_sql() for x in all_operands])
        s += ')'
        if self.negate:
            s = 'not'+s
        return s

with open('cravat/test-filter.json') as f:
    d = json.load(f)
    main_group = FilterGroup(d)
    sql = main_group.get_sql()
    print(sql)