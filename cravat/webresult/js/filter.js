const getAnnotColsByName = (annotName) => {
    for (let i=0; i<filterCols.length; i++) {
        const annotGroup = filterCols[i];
        if (annotGroup.colModel[0].colgroupkey === annotName) {
            return annotGroup
        }
    }
}

const makeFilterColDiv = (filter) => {
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
        .addClass('filter-column-selector');
    colDiv.append(colSel);
    populateFilterColumnSelector(colSel, groupSel.val());

    // Test select
    const testSel = $(getEl('select'))
        .addClass('filter-test-selector')
        .change(filterTestChangeHandler);
    colDiv.append(testSel);
    for (const testName in filterTests) {
        const testDesc = filterTests[testName];
        const testOpt = $(getEl('option'))
            .val(testName)
            .append(testDesc.title);
        testSel.append(testOpt);
    }
    colDiv.append(' ');
    const filterValsSpan = $(getEl('span'))
        .addClass('filter-values-div');
    colDiv.append(filterValsSpan)
    testSel.change();
    
    // Negate
    const negateCheck = $(getEl('input'))
        .addClass('filter-element-negate-check')
        .addClass('filter-column-negate-check')
        .attr('type','checkbox');
    colDiv.append(negateCheck);
    colDiv.append('negate ');
    
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

const filterTestChangeHandler = (event) => {
    const testSel = $(event.target);
    const valuesDiv = testSel.siblings('.filter-values-div');
    const testName = testSel.val();
    populateFilterValues(valuesDiv, testName);

}

const populateFilterValues = (valsContainer, testName, value) => {
    valsContainer.empty();
    const testDesc = filterTests[testName];
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
}

const makeFilterGroupDiv = (filter) => {
    const groupDiv = $(getEl('div'))
        .addClass('filter-group-div')
        .addClass('filter-element-div');
    
    // Elements div
    const elemsDiv = $(getEl('div'))
    .addClass('filter-group-elements-div');
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
    // Operator selector
    controlsDiv.append(' Operator: ')
    const operatorSel = $(getEl('select'))
        .addClass('filter-group-operator-select')
        .change(groupOperatorSelectHandler);
    controlsDiv.append(operatorSel)
    operatorSel.append($(getEl('option')).val('and').append('and'));
    operatorSel.append($(getEl('option')).val('or').append('or'));
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
    elemDiv.prev().remove()
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
        const operator = allElemsDiv
            .siblings()
            .children('.filter-group-operator-select')
            .val();
        const joinOpDiv = $(getEl('div'))
            .addClass('filter-join-operator-div')
            .append(operator);
        allElemsDiv.append(joinOpDiv);
    }
    allElemsDiv.append(elemDiv);
}

const groupOperatorSelectHandler = (event) => {
    const groupOpSel = $(event.target);
    const operator = groupOpSel.val();
    const joinDivs = groupOpSel.parent().siblings('.filter-group-elements-div').children('.filter-join-operator-div');
    joinDivs.empty();
    joinDivs.append(operator);
}

const makeGroupFilter = (groupDiv) => {
    const filter = {};
    // Operator
    const opSel = groupDiv.children().children('.filter-group-operator-select');
    filter.operator = opSel.val();
    const elemsDiv = groupDiv.children('.filter-group-elements-div');
    // Columns
    const colDivs = elemsDiv.children('.filter-column-div');
    filter.columns = [];
    for (let i=0; i<colDivs.length; i++) {
        const colFilter = {}
        const colDiv = $(colDivs[i]);
        // Column
        colFilter.column = colDiv.children('.filter-column-selector').val();
        // Test
        colFilter.test = colDiv.children('.filter-test-selector').val();
        // Value
        const valInputs = colDiv.children('.filter-values-div').children();
        if (valInputs.length === 0) {
            colFilter.value = null;
        } else if (valInputs.length === 1) {
            var rawValue = $(valInputs[0]).val();
            // Below is temporary. Implement categorical column type and remove this.
            if (colFilter.column == 'base__so') {
                rawValue = soDic[rawValue];
            }
            colFilter.value = isNaN(Number(rawValue)) ? rawValue: Number(rawValue);
        } else {
            colFilter.value = [];
            for (let j=0; j<valInputs.length; j++){
                const rawValue = $(valInputs[j]).val()
                colFilter.value.push(Number(rawValue) !== NaN ? Number(rawValue) : rawValue);
            }
        }
        // Negate
        colFilter.negate = colDiv.children('.filter-column-negate-check').is(':checked');
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
    equals: {title:'equals', inputs: 1},
    lessThanEq: {title:'<=', inputs: 1},
    lessThan: {title:'<', inputs:1},
    greaterThanEq: {title:'>=', inputs:1},
    greaterThan: {title:'>', inputs:1},
    hasData: {title:'has data', inputs:0},
    noData: {title:'is empty', inputs:0},
    stringContains: {title: 'contains', inputs:1},
    stringStarts: {title: 'starts with', inputs:1},
    stringEnds: {title: 'ends with', inputs:1},
    between: {title: 'in range', inputs:2}
}
