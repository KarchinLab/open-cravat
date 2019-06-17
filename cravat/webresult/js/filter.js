const getAnnotColsByName = (annotName) => {
    for (let i=0; i<filterCols.length; i++) {
        const annotGroup = filterCols[i];
        if (annotGroup.colModel[0].colgroupkey === annotName) {
            return annotGroup
        }
    }
}

const filterNotToggleClick = (event) => {
    const target = $(event.target);
    const curActive = target.attr('active');
    let newActive;
    if (curActive === 'true') {
        newActive = 'false';
    } else {
        newActive = 'true';
    }
    target.attr('active',newActive);
}

const makeFilterColDiv = (filter, filterLevel) => {
    const colDiv = $(getEl('div'))
        .addClass('filter-column-div')
        .addClass('filter-element-div');
        
    // Annotator select
    const groupSel = $(getEl('select'))
        .addClass('filter-annotator-selector')
        .change(filterGroupChangeHandler);
    colDiv.append(groupSel);
    for (let i=0; i<filterCols.length; i++) {
        var colGroup = filterCols[i];
        let groupOpt = $(getEl('option'))
            .val(colGroup.title)
            .append(colGroup.title);
        groupSel.append(groupOpt);
    };
    
    // Column select
    const colSel = $(getEl('select'))
        .addClass('filter-column-selector')
        .on('change', onFilterColumnSelectorChange);
    colDiv.append(colSel);

    // Not toggle
    const notSpan = $(getEl('span'))
        .addClass('filter-not-toggle')
        .attr('active','false')
        .click(filterNotToggleClick)
        .text('not');
    colDiv.append(notSpan);
    
    // Test select
    const testSel = $(getEl('select'))
        .addClass('filter-test-selector')
        .change(filterTestChangeHandler);
    testSel[0].setAttribute('prevselidx', 0);
    colDiv.append(testSel);
    for (var i = 0; i < filterTestNames.length; i++) {
        var filterTestName = filterTestNames[i];
        const testDesc = filterTests[filterTestName];
        const testOpt = $(getEl('option'))
            .val(filterTestName)
            .append(testDesc.title);
        testSel.append(testOpt);
    }
    colDiv.append(' ');
    const filterValsSpan = $(getEl('span'))
        .addClass('filter-values-div');
    colDiv.append(filterValsSpan)
    
    // Remove column
    const removeColBtn = $(getEl('span'))
        .addClass('filter-element-remove')
        .click(filterColRemoveHandler)
        .text('X');
    colDiv.append(removeColBtn);

    // Populate from filter
    if (filter !== undefined) {
        // Annotator select
        const annotName = filter.column.split('__')[0];
        const annotTitle = getAnnotColsByName(annotName).title;
        groupSel.val(annotTitle);
        // Column select
        populateFilterColumnSelector(colSel, groupSel.val());
        colSel.val(filter.column);
        colSel.change();
        // Test select
        testSel.val(filter.test);
        // Test values
        populateFilterValues(filterValsSpan, filter.test, filter.value);
        // Check negate
        if (filter.negate) {
            notSpan.click();
        }
    } else {
        populateFilterColumnSelector(colSel, groupSel.val());
    }

    return colDiv;
}

const onFilterColumnSelectorChange = (evt) => {
    var groupName = evt.target.previousSibling.value;
    var columns = null;
    for (var i = 0; i < filterCols.length; i++) {
        if (filterCols[i].title == groupName) {
            columns = filterCols[i].colModel;
            break;
        }
    }
    var columnName = evt.target.value;
    var filter = null;
    var column = null;
    for (var i = 0; i < columns.length; i++) {
        column = columns[i];
        if (column.col == columnName) {
            filter = column.filter;
            break;
        }
    }
    var selColType = column.type;
    if (filter != null) {
        var testDiv = $(evt.target).siblings('.filter-test-selector')[0];
        const $testSel = $(testDiv);
        $testSel.empty();
        for (let i=0; i<filterTestNames.length; i++) {
            var filterTestName = filterTestNames[i];
            const testDesc = filterTests[filterTestName];
            if (testDesc.colTypes.includes(selColType)) {
                const testOpt = $(getEl('option'))
                    .val(filterTestName)
                    .append(testDesc.title);
                $testSel.append(testOpt);
            }
        }
        if (filter.type == 'select') {
            $testSel.append($(getEl('option'))
                .val('select')
                .append(filterTests.select.title)
            );
            var selIdx = null;
            for (var i = 0; i < testDiv.options.length; i++) {
                var option = testDiv.options[i];
                if (option.value == 'select') {
                    var selIdx = i;
                    break;
                }
            }
            if (selIdx) {
                testDiv.selectedIndex = selIdx;
                var event = new Event('change');
                testDiv.dispatchEvent(event);
            }
        } else {
            if (testDiv == null) {
                return;
            }
            for (var i = 0; i < filterTestNames.length; i++) {
                if (filterTests[testDiv.options[i].value].colTypes.indexOf(selColType) >= 0) {
                    testDiv.selectedIndex = i;
                    var event = new Event('change');
                    testDiv.dispatchEvent(event);
                    break;
                }
            }
        }
    }
}

function getFilterColByName (name) {
    var column = null;
    for (var i = 0; i < filterCols.length; i++) {
        var fg = filterCols[i].colModel;
        for (var j = 0; j < fg.length; j++) {
            var col = fg[j];
            if (col.col == name) {
                column = col;
                break;
            }
        }
    }
    return column;
}

const filterTestChangeHandler = (event) => {
    const testSel = $(event.target);
    const valuesDiv = testSel.siblings('.filter-values-div');
    const testName = testSel.val();
    populateFilterValues(valuesDiv, testName);
    testSel[0].setAttribute('prevselidx', testSel[0].selectedIndex);
}

function swapJson (d) {
    var newd = {};
    for (var k in d) {
        newd[d[k]] = k;
    }
    return newd;
}

const populateFilterValues = (valsContainer, testName, value) => {
    valsContainer.empty();
    const testDesc = filterTests[testName];
    var testDiv = valsContainer.siblings('.filter-column-selector');
    var col = testDiv[0].value;
    var column = getFilterColByName(col);
    var filter = column.filter;
    var valSubDic = column.reportsub;
    var valSubDicKeys = Object.keys(valSubDic);
    if (testName == 'select' && filter.type == 'select') {
        var select = getEl('select');
        select.className = 'filter-value-input';
        select.multiple = 'multiple';
        addEl(valsContainer[0], select);
        var optionValues = column.filter.options;
        var writtenOptionValues = [];
        var valToKeys = null;
        if (valSubDicKeys.length == 0) {
            valToKeys = {};
            for (var i = 0; i < optionValues.length; i++) {
                var val = optionValues[i];
                valToKeys[val] = [val];
            }
        } else {
            valToKeys = swapJson(valSubDic);
        }
        /*
        if (value != undefined) {
            for (var j = 0; j < value.length; j++) {
                for (let k = 0; k < valSubDicKeys.length; k++) {
                    const key = valSubDicKeys[k];
                    value[j] = value[j].replace(new RegExp('\\b' + key + '\\b', 'g'), valSubDic[key]);
                }
            }
        }
        */
        if (optionValues != undefined) {
            for (var j = 0; j < optionValues.length; j++) {
                var optionValue = optionValues[j];
                if (optionValue == null) {
                    continue;
                }
                /*
                for (let k = 0; k < valSubDicKeys.length; k++) {
                    const key = valSubDicKeys[k];
                    optionValue = optionValue.replace(new RegExp('\\b' + key + '\\b', 'g'), valSubDic[key]);
                }
                */
                let vals = optionValue.split(';');
                for (let k = 0; k < vals.length; k++) {
                    let val = vals[k];
                    var keys = valToKeys[val];
                    if (writtenOptionValues.indexOf(val) < 0) {
                        writtenOptionValues.push(val);
                        var option = getEl('option');
                        if (keys == undefined) {
                            option.value = val;
                        } else {
                            option.value = keys[0];
                        }
                        option.textContent = val;
                        if (value != undefined && keys != undefined) {
                            for (var l = 0; l < value.length; l++) {
                                for (var m = 0; m < keys.length; m++) {
                                    if (value[l] == keys[m]) {
                                        option.selected = true;
                                        break;
                                    }
                                }
                                if (option.selected == true) {
                                    break;
                                }
                            }
                        }
                        addEl(select, option);
                    }
                }
            }
        }
        if (writtenOptionValues.length > 3) {
            $(select).pqSelect({
                checkbox: true, 
                displayText: '{0} selected',
                singlePlaceholder: '&#x25BD;',
                multiplePlaceholder: '&#x25BD;',
                maxDisplay: 0,
                width: 200,
                search: false,
                selectallText: 'Select all',
            });
        } else {
            $(select).pqSelect({
                checkbox: true, 
                displayText: '{0} selected',
                singlePlaceholder: '&#x25BD;',
                multiplePlaceholder: '&#x25BD;',
                maxDisplay: 0,
                width: 200,
                search: false,
                selectallText: '',
            });
        }
        select.nextSibling.classList.add('ui-state-hover');
    } else {
        for (let i=0; i<testDesc.inputs; i++) {
            const valueInput = $(getEl('input'))
                .addClass('filter-value-input');
                valsContainer.append(valueInput);
                valsContainer.append(' ');
            if (value !== undefined) {
                if (Array.isArray(value)) {
                    valueInput.val(value[i]);
                } else {
                    valueInput.val(value);
                }
            }
        }
    }
}

const filterGroupChangeHandler = (event) => {
    const groupSel = $(event.target);
    const groupTitle = groupSel.val();
    const colSel = groupSel.siblings('.filter-column-selector');
    populateFilterColumnSelector(colSel, groupTitle);
}

const populateFilterColumnSelector = (colSel, groupTitle) => {
    let allCols;
    for (let i=0; i<filterCols.length; i++) {
        var colGroup = filterCols[i];
        if (colGroup.title === groupTitle) {
            allCols = colGroup.colModel;
            break;
        }
    }
    colSel.empty();
    if (allCols === undefined) {
        return;
    }
    const useAllCols = $('.filter-level-button').hasClass('filter-level-advanced');
    for (let i=0; i<allCols.length; i++) {
        const col = allCols[i];
        if (useAllCols || col.filterable ) {
            const colOpt = $(getEl('option'))
                .val(col.col)
                .append(col.title);
            colSel.append(colOpt);
        }
    }
    colSel[0].selectedIndex = 0;
    var event = new Event('change');
    colSel[0].dispatchEvent(event);
}

function makeFilterJson () {
    var filterRootGroupDiv = $('#filter-root-group-div-simple');
    if (filterRootGroupDiv[0].style.display != 'none') {
        var filter = makeGroupFilter(filterRootGroupDiv);
        filterJson = {'variant': filter};
    } else {
        var filterRootGroupDiv = $('#filter-root-group-div-advanced');
        if (filterRootGroupDiv[0].style.display != 'none') {
            var filter = makeGroupFilter(filterRootGroupDiv);
            filterJson = {'variant': filter};
        }
    }
}

function makeFilterRootGroupDiv (filter, name, filterLevel) {
    var filterToShow = filter;
    if (filter != undefined && filter.variant != undefined) {
        filterToShow = filter.variant;
    }
    var filterRootGroupDiv = makeFilterGroupDiv(filterToShow, filterLevel);
    filterRootGroupDiv[0].id = name;
    filterRootGroupDiv.css('margin-left', '0px');
	filterRootGroupDiv.children('.filter-element-remove').attr('hidden', 'true');
	const rootElemsDiv = filterRootGroupDiv.children('.filter-group-div').children('.filter-group-elements-div');
    return filterRootGroupDiv;
}

const makeFilterGroupDiv = (filter, filterLevel) => {
    const wrapperDiv = $(getEl('div'))
        .addClass('filter-group-wrapper-div')
        .addClass('filter-element-div');
    // Not toggle
    if (filterLevel == 'advanced') {
        const notToggle = $(getEl('div'))
            .addClass('filter-not-toggle')
            .attr('active','false')
            .click(filterNotToggleClick)
            .text('not');
        wrapperDiv.append(notToggle);
    }
    // Group div
    const groupDiv = $(getEl('div'))
        .addClass('filter-group-div')
        .addClass('filter-level-' + filterLevel)
        .addClass('filter-element-div');
        wrapperDiv.append(groupDiv);
    // Remove
    const removeDiv = $(getEl('div'))
        .addClass('filter-element-remove')
        .click(filterGroupRemoveHandler)
        .text('X');
    wrapperDiv.append(removeDiv);
    
    // Elements div
    const elemsDiv = $(getEl('div'))
        .addClass('filter-group-elements-div')
        .attr('join-operator','AND');
    groupDiv.append(elemsDiv);
        
    // Controls div
    const controlsDiv = $(getEl('div'))
        .addClass('filter-group-controls-div');
    groupDiv.append(controlsDiv);
    // Add column
    const addRuleDiv = $(getEl('div'))
        .addClass('filter-add-elem-div')
    controlsDiv.append(addRuleDiv);
    const addRuleBtn = $(getEl('button'))
        .text('+')
        .addClass('filter-control-button')
        .click(function (evt) {
            addFilterRuleHandler(evt, filterLevel);
        })
        .attr('title','Add rule');
    addRuleDiv.append(addRuleBtn);
    /// Add group
    if (filterLevel == 'advanced') {
        const addGroupDiv = $(getEl('div'))
            .addClass('filter-add-elem-div')
        controlsDiv.append(addGroupDiv);
        const addGroupBtn = $(getEl('button'))
            .text('( )')
            .addClass('filter-control-button')
            .click(function (evt) {
                addFilterGroupHandler(evt, filterLevel);
            })
            .attr('title','Add group');
        addGroupDiv.append(addGroupBtn);
    }
    // Populate from filter
    if (filter !== undefined && !$.isEmptyObject(filter)) {
        if (filter.operator != undefined) {
            // Assign operator
            elemsDiv.attr('join-operator',filter.operator);
            const joinOperators = elemsDiv.children('.filter-join-operator-div');
            if (joinOperators.length > 0) {
                $(joinOperators[0]).click();
            }
            // Add groups
            for (let i=0; i<filter.groups.length; i++) {
                addFilterElement(elemsDiv,'group',filter.groups[i], undefined, filterLevel);
            }
            // Add rules
            for (let i=0; i<filter.columns.length; i++) {
                addFilterElement(elemsDiv,'rule',filter.columns[i], undefined, filterLevel);
            }
            // Check negate
            if (filter.negate) {
                notToggle.click();
            }
        }
    } else {
        addFilterElement(elemsDiv,'rule', undefined, filterLevel);
    }
    return wrapperDiv;
}

const filterGroupRemoveHandler = (event) => {
    const target = $(event.target);
    const filterElemDiv = target.parent();
    removeFilterElem(filterElemDiv);
}

const filterColRemoveHandler = (event) => {
    const target = $(event.target);
    const filterElemDiv = target.parent();
    removeFilterElem(filterElemDiv);
}

const removeFilterElem = (elemDiv) => {
    // Remove preceding join operator
    const prevJoinOp = elemDiv.prev('.filter-join-operator-div');
    if (prevJoinOp.length > 0) {
        prevJoinOp.remove();
    } else {
        elemDiv.next('.filter-join-operator-div').remove();
    }
    // Remove element
    elemDiv.remove();
}

const addFilterRuleHandler = (event, filterLevel) => {
    const button = $(event.target);
    const elemsDiv = button.parent().parent().siblings('.filter-group-elements-div');
    addFilterElement(elemsDiv, 'rule', undefined, filterLevel);
}

const addFilterGroupHandler = (event, filterLevel) => {
    const button = $(event.target);
    const elemsDiv = button.parent().parent().siblings('.filter-group-elements-div');
    addFilterElement(elemsDiv, 'group', undefined, filterLevel);
}

const addFilterElement = (allElemsDiv, elementType, filter, filterLevel) => {
    let elemDiv;
    if (elementType === 'group') {
        elemDiv = makeFilterGroupDiv(filter, filterLevel);
    } else if (elementType === 'rule') {
        elemDiv = makeFilterColDiv(filter, filterLevel);
    }
    if (allElemsDiv.children().length > 0) {
        const operator = allElemsDiv.attr('join-operator');
        const joinOpDiv = $(getEl('div'))
            .addClass('filter-join-operator-div')
            .append(operator);
        joinOpDiv.click(groupOperatorClickHandler);
        allElemsDiv.append(joinOpDiv);
    }
    allElemsDiv.append(elemDiv);
}

const groupOperatorClickHandler = (event) => {
    const opDiv = $(event.target);
    const allElemsDiv = opDiv.parent();
    const curOperator = allElemsDiv.attr('join-operator');
    let newOperator;
    if (curOperator === 'AND') {
        newOperator = 'OR';
    } else if (curOperator === 'OR') {
        newOperator = 'AND';
    }
    opDiv.text(newOperator);
    opDiv.siblings('.filter-join-operator-div').text(newOperator);
    allElemsDiv.attr('join-operator',newOperator);
}

function doReportSub (reportsub, reportsubKeys, origVal) {
    for (var k = 0; k < reportsubKeys.length; k++) {
        var key = reportsubKeys[k];
        var val = reportsub[key];
        origVal = origVal.replace(new RegExp(val, 'g'), key);
    }
    return origVal;
}

const makeGroupFilter = (groupDiv) => {
    const filter = {};
    const elemsDiv = groupDiv.children('.filter-group-div').children('.filter-group-elements-div');
    // Operator
    filter.operator = elemsDiv.attr('join-operator');
    // Columns
    const colDivs = elemsDiv.children('.filter-column-div');
    filter.columns = [];
    for (let i=0; i<colDivs.length; i++) {
        const colFilter = {}
        const colDiv = $(colDivs[i]);
        // Column
        colFilter.column = colDiv.children('.filter-column-selector').val();
        var column = getFilterColByName(colFilter.column);
        // Test
        colFilter.test = colDiv.children('.filter-test-selector').val();
        if (column.category == 'multi') {
            colFilter.test = 'multicategory';
        }
        // Value
        const valInputs = colDiv.children('.filter-values-div').children();
        var reportsub = column.reportsub;
        var reportsubKeys = Object.keys(reportsub);
        if (colFilter.test == 'select' || colFilter.test == 'multicategory') {
            var selOptions = valInputs[0].selectedOptions;
            colFilter.value = [];
            for (var j = 0; j < selOptions.length; j++) {
                var optVal = selOptions[j].value;
                colFilter.value.push(doReportSub(reportsub, reportsubKeys, optVal));
            }
            if (colFilter.value.length == 0) {
                continue;
            }
        } else {
            if (valInputs.length === 0) {
                colFilter.value = null;
            } else if (valInputs.length === 1) {
                var rawValue = $(valInputs[0]).val();
                var val = isNaN(Number(rawValue)) ? rawValue: Number(rawValue);
                if (reportsubKeys.length > 0 && (colFilter.test == 'stringContains' || colFilter.test == 'stringStarts' || colFilter.test == 'stringEnds')) {
                    var reportsubValues = Object.values(reportsub);
                    var matchReportsubKeys = [];
                    for (var j = 0; j < reportsubKeys.length; j++) {
                        var key = reportsubKeys[j];
                        var value = reportsubValues[j];
                        if ((colFilter.test == 'stringStarts' && value.startsWith(val)) ||
                            (colFilter.test == 'stringEnds' && value.endsWith(val)) ||
                            (colFilter.test == 'stringContains' && value.includes(val))) {
                            matchReportsubKeys.push(key);
                        }
                    }
                    if (matchReportsubKeys.length > 0) {
                        colFilter.test = 'equals';
                        colFilter.value = matchReportsubKeys;
                    } else {
                        continue;
                    }
                } else {
                    colFilter.value = doReportSub(reportsub, reportsubKeys, val);
                }
            } else {
                colFilter.value = [];
                for (let j=0; j<valInputs.length; j++){
                    const rawValue = $(valInputs[j]).val()
                    var val = Number(rawValue) !== NaN ? Number(rawValue) : rawValue;
                    colFilter.value.push(doReportSub(reportsub, reportsubKeys, val));
                }
            }
        }
        // Negate
        colFilter.negate = colDiv.children('.filter-not-toggle').attr('active') === 'true';
        filter.columns.push(colFilter)
    }
    // Groups
    const groupDivs = elemsDiv.children('.filter-group-wrapper-div');
    filter.groups = [];
    for (let i=0; i<groupDivs.length; i++) {
        subGroupDiv = $(groupDivs[i]);
        subGroupFilter = makeGroupFilter(subGroupDiv);
        filter.groups.push(subGroupFilter);
    }
    
    // Negate
    filter.negate = groupDiv.children('.filter-not-toggle').attr('active') === 'true';
    return filter;
}

const importFilter = () => {
    const json = $('#filter-json').val();
    const filter = JSON.parse(json);
    loadFilter(filter);
}

const loadFilter = (filter) => {
    const mainDiv = $('#main-div');
    mainDiv.empty();
    rootGroupDiv = makeFilterGroupDiv(filter, filterLevel);
    mainDiv.append(rootGroupDiv);
}

const filterTests = {
    equals: {title:'equals', inputs: 1, colTypes: ['string', 'float', 'int', 'select'], },
    lessThanEq: {title:'<=', inputs: 1, colTypes: ['float', 'int']},
    lessThan: {title:'<', inputs:1, colTypes: ['float']},
    greaterThanEq: {title:'>=', inputs:1, colTypes: ['float', 'int']},
    greaterThan: {title:'>', inputs:1, colTypes: ['float']},
    hasData: {title:'has data', inputs:0, colTypes: ['float', 'int', 'string']},
    noData: {title:'is empty', inputs:0, colTypes: ['float', 'int', 'string']},
    stringContains: {title: 'contains', inputs:1, colTypes: ['string']},
    between: {title: 'in range', inputs:2, colTypes: ['float', 'int']},
    select: {title: 'one of', inputs: 1, colTypes: ['select']},
}

const filterTestNames = [
    'hasData',
    'equals',
    'noData',
    'between',
    'lessThanEq',
    'lessThan',
    'greaterThanEq',
    'greaterThan',
    'stringContains',
    'select',
];

