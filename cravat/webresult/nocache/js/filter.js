var filterElemCount = 0
var visibleFilterHoverP = null
var filterDragEnterEl = null

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

const makeFilterElementControlDiv = function () {
    var div = getEl('div')
    div.classList.add('filter-element-control-div')
    div.classList.add('hovercontrol')
    div.addEventListener('click', function (evt) {
        filterGroupRemoveHandler(evt)
    })
    const removeDiv = $(getEl('img'))
        .addClass('filter-element-control-icon')
    removeDiv.attr('src', '/result/images/x.svg')
    div.append(removeDiv[0]);
    return div
}

const addHoverControlEventListener = function (el) {
    el.addEventListener('mouseover', function (evt) {
        showHoverControl(evt)
    })
    el.addEventListener('mouseleave', function (evt) {
        hideHoverControl(evt)
    })
}

const showHoverControl = function (evt) {
    if (visibleFilterHoverP != null) {
        visibleFilterHoverP.classList.remove('hoveredgroup')
        visibleFilterHoverP.querySelectorAll(':scope > .hovercontrol').forEach(el => {
            if (el.getAttribute('active') != 'true') {
                el.style.visibility = 'hidden'
            }
        })
    }
    var p = evt.target.closest('.filter-element-div')
    p.classList.add('hoveredgroup')
    var els = p.querySelectorAll(':scope > .hovercontrol')
    if (els.length > 0) {
        els.forEach(el => {
            el.style.visibility = 'visible'
        })
        visibleFilterHoverP = p
    }
}

const hideHoverControl = function (evt) {
    var p = evt.target.closest('.filter-element-div')
    p.classList.remove('hoveredgroup')
    var els = p.querySelectorAll(':scope > .hovercontrol')
    if (els.length > 0) {
        els.forEach(el => {
            if (el.getAttribute('active') != 'true') {
                el.style.visibility = 'hidden'
            }
        })
        visibleFilterHoverP = null
    }
}

const makeDragHandle = function () {
    const moveDiv = getEl('div')
    moveDiv.classList.add('hovercontrol')
    moveDiv.title = 'Drag and drop to rearrange filters'
    addHoverControlEventListener(moveDiv)
    moveDiv.addEventListener('mousedown', function (evt) {
        evt.target.closest('.filter-element-div').classList.add('dragclicked')
    })
    moveDiv.addEventListener('mouseup', function (evt) {
        evt.target.closest('.filter-element-div').classList.remove('dragclicked')
    })
    var moveImg = getEl('img')
    moveImg.setAttribute('src', '/result/images/grip-vertical.svg')
    moveImg.classList.add('passthrough')
    addEl(moveDiv, moveImg)
    return moveDiv
}

const makeFilterColDiv = (filter) => {
    const colDiv = $(getEl('div'))
        .addClass('filter-column-div')
        .addClass('filter-element-div');
    addHoverControlEventListener(colDiv[0])
    addEl(colDiv[0], makeDragHandle())
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
    // Controls
    var cdiv = makeFilterElementControlDiv()
    colDiv.append(cdiv)
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
                valToKeys[val] = val;
            }
        } else {
            valToKeys = swapJson(valSubDic);
        }
        if (optionValues != undefined) {
            for (var j = 0; j < optionValues.length; j++) {
                var optionValue = optionValues[j];
                if (optionValue == null) {
                    continue;
                }
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
                            option.value = keys;
                        }
                        option.textContent = val;
                        if (value != undefined && keys != undefined) {
                            for (var l = 0; l < value.length; l++) {
                                if (value[l] === keys) {
                                    option.selected = true;
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
    for (let i=0; i<allCols.length; i++) {
        const col = allCols[i];
        if (filterMgr.qbBannedColumns.indexOf(col.col) > -1) {
            continue;
        }
        const colOpt = $(getEl('option'))
            .val(col.col)
            .append(col.title);
        colSel.append(colOpt);
    }
    colSel[0].selectedIndex = 0;
    var event = new Event('change');
    colSel[0].dispatchEvent(event);
}

function makeFilterRootGroupDiv (filter, name, filterLevel) {
    var filterToShow = filter;
    if (filter != undefined && filter.variant != undefined) {
        filterToShow = filter.variant;
    }
    var filterRootGroupDiv = makeFilterGroupDiv(filterToShow);
    filterRootGroupDiv[0].id = name;
    filterRootGroupDiv.css('margin-left', '0px');
	filterRootGroupDiv.children('.filter-element-remove').attr('hidden', 'true');
	const rootElemsDiv = filterRootGroupDiv.children('.filter-group-div').children('.filter-group-elements-div');
    return filterRootGroupDiv;
}

const makeFilterGroupDiv = (filter) => {
    // Group div
    const groupDiv = $(getEl('div'))
        .addClass('filter-group-div')
        .addClass('filter-element-div');
    addHoverControlEventListener(groupDiv[0])
    addEl(groupDiv[0], makeDragHandle())
    // Elements div
    const operator = 'and'
    var elemsDiv = getEl('div')
    elemsDiv.classList.add('filter-group-elements-div')
    elemsDiv.setAttribute('join-operator', operator)
    addEl(groupDiv[0], elemsDiv)
    // Join
    addEl(elemsDiv, makeJoinOperatorDiv(operator)[0])
    // Remove
    var cdiv = makeFilterElementControlDiv()
    cdiv.classList.add('hovercontrol')
    cdiv.classList.add('x')
    addHoverControlEventListener(cdiv)
    groupDiv.append(cdiv)
    // Not toggle
    var notToggle = getEl('div')
    notToggle.classList.add('filter-not-toggle')
    notToggle.classList.add('hovercontrol')
    notToggle.classList.add('negate')
    notToggle.setAttribute('active','false')
    notToggle.addEventListener('click', function (evt) {
        filterNotToggleClick(evt)
    })
    addEl(notToggle, getTn('NOT'))
    addHoverControlEventListener(notToggle)
    groupDiv.append(notToggle);
    const addRuleBtn = $(getEl('button'))
        .text('+')
        .addClass('filter-control-button')
        .addClass('butn')
        .addClass('addrule')
        .addClass('hovercontrol')
        .click(function (evt) {
            addFilterRuleHandler(evt);
        })
        .attr('title','Add rule');
    groupDiv.append(addRuleBtn);
    const addGroupBtn = $(getEl('button'))
        .text('( )')
        .addClass('filter-control-button')
        .addClass('butn')
        .addClass('addgroup')
        .addClass('hovercontrol')
        .click(function (evt) {
            addFilterGroupHandler(evt);
        })
        .attr('title','Add group');
    groupDiv.append(addGroupBtn);
    // Populate from filter
    if (filter !== undefined && !$.isEmptyObject(filter)) {
        if (filter.operator != undefined) {
            // Assign operator
            elemsDiv.setAttribute('join-operator', filter.operator)
            /*const joinOperators = $(elemsDiv).children('.filter-join-operator-div');
            if (joinOperators.length > 0) {
                $(joinOperators[0]).click();
            }*/
            // Add rules
            for (let i=0; i<filter.rules.length; i++) {
                let rule = filter.rules[i];
                if (rule.hasOwnProperty('operator')) {
                    addFilterElement($(elemsDiv),'group', rule, undefined);
                } else {
                    addFilterElement($(elemsDiv),'rule', rule, undefined);
                }
            }
            // Check negate
            if (filter.negate) {
                notToggle.click();
            }
        }
    } else {
        addFilterElement($(elemsDiv),'rule', undefined);
    }
    return groupDiv;
}

const filterGroupRemoveHandler = (event) => {
    const filterElemDiv = $(event.target.closest(".filter-element-div"))
    removeFilterElem(filterElemDiv);
}

/*const filterColRemoveHandler = (event) => {
    const filterElemDiv = $(event.target.closest(".filter-element-div"))
    removeFilterElem(filterElemDiv);
}*/

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

const addFilterRuleHandler = (event) => {
    const button = event.target
    const elemsDiv = $(button.closest('.filter-group-div').querySelector('div.filter-group-elements-div'))
    addFilterElement(elemsDiv, 'rule', undefined);
}

const addFilterGroupHandler = (event) => {
    const button = event.target
    const elemsDiv = $(button.closest('.filter-group-div').querySelector('div.filter-group-elements-div'))
    addFilterElement(elemsDiv, 'group', undefined);
}

const makeJoinOperatorDiv = function (operator) {
    const joinOpDiv = $(getEl('div'))
        .addClass('filter-join-operator-div')
        .addClass('filter-drop-target')
    joinOpDiv.click(groupOperatorClickHandler);
    joinOpDiv[0].addEventListener('dragenter', function (evt) {
        joinOpDiv[0].classList.add('dragenter')
        evt.preventDefault()
    })
    joinOpDiv[0].addEventListener('dragleave', function (evt) {
        joinOpDiv[0].src = '/result/images/arrow-down-right-circle.svg'
        joinOpDiv[0].classList.remove('dragenter')
    })
    joinOpDiv[0].addEventListener('dragover', function (evt) {
        evt.preventDefault()
    })
    joinOpDiv[0].addEventListener('drop', function (evt) {
        var source = document.querySelector('#' + evt.dataTransfer.getData('text/plain'))
        var target = evt.target
        if (source.nextSibling == target || target.nextSibling == source) {
            return
        }
        source.previousSibling.remove()
        var p = target.closest('.filter-group-elements-div')
        addEl(p, source)
        p.insertBefore(source, target)
        if (source.previousSibling == null || source.previousSibling.classList.contains('filter-join-operator-div') == false) {
            var newj = makeJoinOperatorDiv(p.getAttribute('join-operator'))[0]
            p.insertBefore(newj, source)
        }
        if (source.nextSibling == null || source.nextSibling.classList.contains('filter-join-operator-div') == false) {
            var newj = makeJoinOperatorDiv(p.getAttribute('join-operator'))[0]
            p.insertBefore(newj, source)
            p.insertBefore(source, newj)
        }
        document.querySelector('#qb-root').querySelectorAll('.filter-join-operator-div').forEach(el => {
            el.classList.remove('dragenter')
        })
        evt.preventDefault()
    })
    return joinOpDiv
}

const addFilterElement = (allElemsDiv, elementType, filter) => {
    let elemDiv;
    if (elementType === 'group') {
        elemDiv = makeFilterGroupDiv(filter);
    } else if (elementType === 'rule') {
        elemDiv = makeFilterColDiv(filter);
    }
    elemDiv[0].id = 'filter-element-' + filterElemCount
    filterElemCount += 1
    elemDiv[0].setAttribute('draggable', true)
    elemDiv[0].addEventListener('dragstart', function (evt) {
        evt.dataTransfer.setData('text/plain', evt.target.id)
        evt.dataTransfer.dropEffect = 'move'
        filterDragEnterEl = evt.target.id
        document.querySelector('#qb-root').classList.add('dragstarted')
    })
    elemDiv[0].addEventListener('dragend', function (evt) {
        document.querySelector('#qb-root').classList.remove('dragstarted')
        evt.target.closest('.filter-element-div').classList.remove('dragclicked')
    })
    allElemsDiv.append(elemDiv);
    //if (allElemsDiv.children().length > 0) {
        const operator = allElemsDiv.attr('join-operator');
        const joinOpDiv = makeJoinOperatorDiv(operator)
        allElemsDiv.append(joinOpDiv);
    //}
}

const groupOperatorClickHandler = (event) => {
    const opDiv = $(event.target);
    const allElemsDiv = opDiv.parent();
    const curOperator = allElemsDiv.attr('join-operator');
    let newOperator
    if (curOperator.toLowerCase() === 'and') {
        newOperator = 'or';
    } else if (curOperator.toLowerCase() === 'or') {
        newOperator = 'and';
    }
    allElemsDiv.attr('join-operator', newOperator);
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
    const elemsDiv = groupDiv.children('.filter-group-elements-div')
    // Operator
    filter.operator = elemsDiv.attr('join-operator');
    // Columns
    const colDivs = elemsDiv.children('.filter-column-div');
    filter.rules = [];
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
        colFilter.column = colFilter.column==='base__tags' ? 'tagsampler__tags' : colFilter.column //TODO: unhack
        filter.rules.push(colFilter)
    }
    // Groups
    const groupDivs = elemsDiv.children('.filter-group-div');
    for (let i=0; i<groupDivs.length; i++) {
        subGroupDiv = $(groupDivs[i]);
        subGroupFilter = makeGroupFilter(subGroupDiv);
        filter.rules.push(subGroupFilter);
    }
    // Negate
    filter.negate = groupDiv.children('.filter-not-toggle').attr('active') === 'true';
    return filter;
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

