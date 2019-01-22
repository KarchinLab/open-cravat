const getAnnotColsByName = (annotName) => {
    for (let i=0; i<filterCols.length; i++) {
        const annotGroup = filterCols[i];
        if (annotGroup.colModel[0].colgroupkey === annotName) {
            return annotGroup
        }
    }
}

const filterNotToggleClick = (event) => {
    console.log('Not toggle');
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

const makeFilterColDiv = (filter) => {
    const colDiv = $(getEl('div'))
        .addClass('filter-column-div')
        .addClass('filter-element-div');
    // Not toggle
    const notSpan = $(getEl('span'))
        .addClass('filter-not-toggle')
        .attr('active','false')
        .click(filterNotToggleClick)
        .text('not');
    colDiv.append(notSpan);
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
        .addClass('filter-column-selector');
    colSel.on('change', onFilterColumnSelectorChange);
    colDiv.append(colSel);
    populateFilterColumnSelector(colSel, groupSel.val());

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
    testSel.change();
    
    // Remove column
    const removeColBtn = $(getEl('button'))
    .addClass('filter-element-remove-button')
    .addClass('filter-column-remove-button')
    .click(filterColRemoveHandler)
    .append('X');
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
        // Test select
        testSel.val(filter.test);
        // Test values
        populateFilterValues(filterValsSpan, filter.test, filter.value);
        // Check negate
        negateCheck[0].checked = filter.negate;
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
    if (filter != null) {
        var testDiv = evt.target.nextSibling;
        if (filter.type == 'select') {
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
            var curTestKey = testDiv.value;
            var curTestSetup = filterTests[curTestKey];
            var curTestColTypes = curTestSetup['colTypes'];
            var selColType = column.type;
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
    var testDiv = testSel[0].previousSibling;
    var colname = testDiv.value;
    var colType = getFilterColByName(colname).type;
    var selTestType = testSel[0].value;
    var filterTest = filterTests[selTestType];
    var allowedColTypes = filterTest.colTypes;
    if (allowedColTypes.indexOf(colType) < 0) {
        testSel[0].selectedIndex = testSel[0].getAttribute('prevselidx');
        return;
    }
    populateFilterValues(valuesDiv, testName);
    testSel[0].setAttribute('prevselidx', testSel[0].selectedIndex);
}

const populateFilterValues = (valsContainer, testName, value) => {
    valsContainer.empty();
    const testDesc = filterTests[testName];
    var testDiv = valsContainer[0].previousSibling.previousSibling.previousSibling;
    var col = testDiv.value;
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
        if (optionValues != undefined) {
            for (var j = 0; j < optionValues.length; j++) {
                var optionValue = optionValues[j];
                if (optionValue == null) {
                    continue;
                }
                for (let k = 0; k < valSubDicKeys.length; k++) {
                    const key = valSubDicKeys[k];
                    optionValue = optionValue.replace(new RegExp(key, 'g'), valSubDic[key]);
                }
                let vals = optionValue.split(';');
                for (let k = 0; k < vals.length; k++) {
                    let val = vals[k];
                    if (writtenOptionValues.indexOf(val) < 0) {
                        writtenOptionValues.push(val);
                        var option = getEl('option');
                        option.value = val;
                        option.textContent = val;
                        addEl(select, option);
                    }
                }
            }
        }
        $(select).pqSelect({
            checkbox: true, 
            displayText: '{0} selected',
            singlePlaceholder: '>',
            multiplePlaceholder: '>',
            maxDisplay: 0,
            width: 200,
        });
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
    for (let i=0; i<allCols.length; i++) {
        const col = allCols[i];
        const colOpt = $(getEl('option'))
            .val(col.col)
            .append(col.title);
        colSel.append(colOpt);
    }
    colSel[0].selectedIndex = 0;
    var event = new Event('change');
    colSel[0].dispatchEvent(event);
}

const makeFilterGroupDiv = (filter) => {
    const groupDiv = $(getEl('div'))
        .addClass('filter-group-div')
        .addClass('filter-element-div');
    
    // Elements div
    const elemsDiv = $(getEl('div'))
        .addClass('filter-group-elements-div')
        .attr('join-operator','and');
    groupDiv.append(elemsDiv);
        
    // Controls div
    const controlsDiv = $(getEl('div'))
        .addClass('filter-group-controls-div');
        groupDiv.append(controlsDiv);
    // Add column
    const addColumnBtn = $(getEl('button'))
        .addClass('filter-add-column-btn')
        .click(addFilterColBtnHandler)
        .append('Add column');
    controlsDiv.append(addColumnBtn).append(' ');
    // Add group
    const addGroupBtn = $(getEl('button'))
        .addClass('filter-add-group-btn')
        .click(addFilterGroupBtnHandler)
        .append('Add group');
    controlsDiv.append(addGroupBtn).append(' ');
    // Negate
    const negateCheck = $(getEl('input'))
        .addClass('filter-element-negate-check')
        .addClass('filter-group-negate-check')
        .attr('type','checkbox');
    controlsDiv.append(negateCheck);
    controlsDiv.append('negate ');
    // Remove
    const removeBtn = $(getEl('button'))
    .addClass('filter-element-remove-btn')
    .addClass('filter-group-remove-btn')
    .click(filterGroupRemoveHandler)
    .append('X');
    controlsDiv.append(' ').append(removeBtn);
    
    // Populate from filter
    if (filter !== undefined) {
        if (filter.operator != undefined) {
            // Assign operator
            operatorSel.val(filter.operator);
            // Add groups
            for (let i=0; i<filter.groups.length; i++) {
                addFilterElement(elemsDiv,'group',filter.groups[i]);
            }
            // Add columns
            for (let i=0; i<filter.columns.length; i++) {
                addFilterElement(elemsDiv,'column',filter.columns[i]);
            }
            // Check negate
            negateCheck[0].checked = filter.negate;
        }
    }
    return groupDiv;
}

const filterGroupRemoveHandler = (event) => {
    const target = $(event.target);
    const filterElemDiv = target.parent().parent()
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

const addFilterColBtnHandler = (event) => {
    const button = $(event.target);
    const elemsDiv = button.parent().siblings('.filter-group-elements-div');
    addFilterElement(elemsDiv, 'column');
}

const addFilterGroupBtnHandler = (event) => {
    const button = $(event.target);
    const elemsDiv = button.parent().siblings('.filter-group-elements-div');
    addFilterElement(elemsDiv, 'group');
}

const addFilterElement = (allElemsDiv, elementType, filter) => {
    let elemDiv;
    if (elementType === 'group') {
        elemDiv = makeFilterGroupDiv(filter);
    } else if (elementType === 'column') {
        elemDiv = makeFilterColDiv(filter);
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
    if (curOperator === 'and') {
        newOperator = 'or';
    } else if (curOperator === 'or') {
        newOperator = 'and';
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
    const elemsDiv = groupDiv.children('.filter-group-elements-div');
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
                if (column.type == 'string') {
                    colFilter.value = '';
                } else {
                    colFilter.value = null;
                }
            } else if (valInputs.length === 1) {
                var rawValue = $(valInputs[0]).val();
                var val = isNaN(Number(rawValue)) ? rawValue: Number(rawValue);
                colFilter.value = doReportSub(reportsub, reportsubKeys, val);
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
    const groupDivs = elemsDiv.children('.filter-group-div');
    filter.groups = [];
    for (let i=0; i<groupDivs.length; i++) {
        groupDiv = $(groupDivs[i]);
        groupFilter = makeGroupFilter(groupDiv);
        filter.groups.push(groupFilter);
    }
    
    // Negate
    filter.negate = groupDiv.children().children('.filter-group-negate-check').is(':checked');

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
    rootGroupDiv = makeFilterGroupDiv(filter);
    mainDiv.append(rootGroupDiv);
}

const filterTests = {
    equals: {title:'equals', inputs: 1, colTypes: ['string', 'float', 'int', 'select'], },
    lessThanEq: {title:'<=', inputs: 1, colTypes: ['float', 'int']},
    lessThan: {title:'<', inputs:1, colTypes: ['float', 'int']},
    greaterThanEq: {title:'>=', inputs:1, colTypes: ['float', 'int']},
    greaterThan: {title:'>', inputs:1, colTypes: ['float', 'int']},
    hasData: {title:'has data', inputs:0, colTypes: ['float', 'int', 'string']},
    noData: {title:'is empty', inputs:0, colTypes: ['float', 'int', 'string']},
    stringContains: {title: 'contains', inputs:1, colTypes: ['string']},
    stringStarts: {title: 'starts with', inputs:1, colTypes: ['string']},
    stringEnds: {title: 'ends with', inputs:1, colTypes: ['string']},
    between: {title: 'in range', inputs:2, colTypes: ['float', 'int']},
    select: {title: 'select', inputs: 1, colTypes: ['string', 'float', 'int']},
}

const filterTestNames = [
    'equals',
    'between',
    'lessThanEq',
    'lessThan',
    'greaterThanEq',
    'greaterThan',
    'hasData',
    'noData',
    'stringContains',
    'stringStarts',
    'stringEnds',
    'select',
];

