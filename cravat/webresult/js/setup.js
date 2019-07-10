function setupAllTabs () {
	for (var i = 0; i < resultLevels.length; i++) {
		var level = resultLevels[i];
		setupTab(level);
	}
}

function setupTab (tabName) {
	if (resetTab[tabName] == false) {
		return;
	}

	var tabDiv = document.getElementById("tab_" + tabName);

	var rightDivId = 'rightdiv_' + tabName;
	var rightDiv = document.getElementById(rightDivId);
	if (rightDiv == null) {
		rightDiv = getEl('div');
		rightDiv.id = rightDivId;
		rightDiv.className = 'rightdiv';
		addEl(tabDiv, rightDiv);
	}

	// Populates the right panel.
	if (tabName == 'info') {
		makeInfoTab(rightDiv);
	} else if (tabName == 'variant' || tabName == 'gene') {
		makeVariantGeneTab(tabName, rightDiv);
	} else if (tabName == 'sample' || tabName == 'mapping') {
		makeSampleMappingTab(tabName, rightDiv);
	} else if (tabName == 'filter') {
		makeFilterTab(rightDiv);
	}
	addEl(tabDiv, rightDiv);

	setupEvents(tabName);

	if (tabName != 'info' && tabName != 'filter') {
		var stat = infomgr.getStat(tabName);
		var columns = infomgr.getColumns(tabName);
		var data = infomgr.getData(tabName);
		dataLengths[tabName] = data.length;

		makeGrid(columns, data, tabName);
		$grids[tabName].pqGrid('refreshDataAndView');

		// Selects the first row.
		if (tabName == currentTab) {
			if (stat['rowsreturned'] && stat['norows'] > 0) {
				selectedRowIds[tabName] = null;
				$grids[tabName].pqGrid('setSelection', {rowIndx : 0, colIndx: 0, focus: true});
                selectedRowNos[tabName] = 0;
			}
		}
	}

	resetTab[tabName] = false;

	placeDragNSBar(tabName);
	placeCellValueDiv(tabName);

	if (loadedTableSettings != undefined && loadedTableSettings[currentTab] != undefined) {
		applyTableSetting(currentTab);
	}
	if (loadedViewerWidgetSettings != undefined && loadedViewerWidgetSettings[currentTab] != undefined) {
		applyWidgetSetting(currentTab);
	}
    if ((currentTab == 'variant' || currentTab == 'gene') && tableDetailDivSizes[currentTab] != undefined) {
        applyTableDetailDivSizes();
    }
	changeMenu();
}

function filterHeaderClick (event) {
	$(this).toggleClass('inactive');
}

function makeFilterTab (rightDiv) {
	if (smartFilters === undefined) { 
		return;
	}
	rightDiv = $(rightDiv);
	// Sample selector
	let sampleContainer = $(getEl('div'))
		.addClass('filter-section');
	rightDiv.append(sampleContainer);
	let sampleHeader = $(getEl('div'))
		.addClass('filter-header')
		.click(filterHeaderClick)
		.addClass('inactive');
	sampleContainer.append(sampleHeader);
	sampleHeader.append($(getEl('span'))
		.addClass('filter-header-arrow')
	)
	sampleHeader.append($(getEl('span'))
		.addClass('filter-header-text')
		.text('Samples')
	)
	let sampleContent = $(getEl('div'))
		.addClass('filter-content');
	sampleContainer.append(sampleContent);
	sampleContent.append($(getEl('p'))
		.text('Click sample IDs once to include only variants in that sample. Click twice to exclude variants from that sample.')
	)
	let sampleSelDiv = $(getEl('div'))
		.attr('id','sample-select-cont');
	sampleContent.append(sampleSelDiv);
	let sampleIds = getFilterCol('tagsampler__samples').categories;
	let maxLen = sampleIds.reduce((a,b) => {return a.length>b.length ? a : b}).length;
	maxLen = maxLen > 25 ? 25 : maxLen;
	let sboxMaxWidth = `${maxLen}ch`;
	for (let i=0; i<sampleIds.length; i++) {
		let sid = sampleIds[i];
		let sampleBox = $(getEl('div'))
			.addClass('sample-selector')
			.click(onSampleSelectorClick)
			.addClass('sample-neutral')
			.css('max-width', sboxMaxWidth)
			.attr('title', sid);
		sampleSelDiv.append(sampleBox);
		sampleBox.append($(getEl('span'))
			.addClass('sample-state-span')
		)
		sampleBox.append($(getEl('span'))
			.text(sid)
			.addClass('sample-selector-label')
		)
	}
	// Gene selector
	let geneContainer = $(getEl('div'))
		.addClass('filter-section');
	rightDiv.append(geneContainer);
	let geneHeader = $(getEl('div'))
		.addClass('filter-header')
		.click(filterHeaderClick)
		.addClass('inactive');
	geneContainer.append(geneHeader);
	geneHeader.append($(getEl('span'))
		.addClass('filter-header-arrow')
	)
	geneHeader.append($(getEl('span'))
		.addClass('filter-header-text')
		.text('Genes')
	)
	let geneContent = $(getEl('div'))
		.addClass('filter-content');
	geneContainer.append(geneContent);
	geneContent.append($(getEl('p'))
		.text('Type a list of gene names to include. One per line. Or, load a gene list from a file.')
	)
	let geneTextArea = $(getEl('textarea'))
		.attr('id','gene-list-text')
		.change(onGeneListSelectorChange);
	geneContent.append(geneTextArea);
	let geneFileInput = $(getEl('input'))
		.attr('type','file')
		.attr('id','gene-list-file')
		.change(onGeneListSelectorChange);
	geneContent.append(geneFileInput);

	// Smartfilters
	let vPropContainer = $(getEl('div'))
		.addClass('filter-section')
		rightDiv.append(vPropContainer);
	let vPropHeader = $(getEl('div'))
		.addClass('filter-header')
		.click(filterHeaderClick);
	vPropContainer.append(vPropHeader);
	vPropHeader.append($(getEl('span'))
		.addClass('filter-header-arrow')
	)
	vPropHeader.append($(getEl('span'))
		.text('Variant Properties')
	)
	let vPropContent = $(getEl('div'))
		.addClass('filter-content');
	vPropContainer.append(vPropContent);
	fTypeDiv = $(getEl('div'));
	vPropContent.append(fTypeDiv);
	let vPropSel = $(getEl('select'))
		.attr('id','vprop-sel')
		.append($(getEl('option')).val('sf').text('sf'))
		.append($(getEl('option')).val('qb').text('qb'))
		.css('display','none')
		.change(vPropSelectChange);
	fTypeDiv.append(vPropSel);
	fTypeDiv.append(
		$(getEl('span'))
		.addClass('vprop-option')
		.text('Smart Filters')
		.click(vPropOptionClick)
		.attr('value','sf')
		.addClass('active')
	);
	fTypeDiv.append(
		$(getEl('span'))
		.addClass('vprop-option')
		.text('Query Builder')
		.click(vPropOptionClick)
		.attr('value','qb')
	);
	sfContent = $(getEl('div'))
		.attr('id','vprop-sf');
	vPropContent.append(sfContent);
	
	sfContent.append($(getEl('p'))
		.text('Click a filter to apply it.')
	)
	let orderedSources = Object.keys(smartFilters);
	orderedSources.splice(orderedSources.indexOf('base'), 1);
	orderedSources.sort();
	orderedSources = ['base'].concat(orderedSources)
	for (let i=0; i<orderedSources.length; i++){
		let sfSource = orderedSources[i];
		let sfGroup = smartFilters[sfSource];
		for (let j=0; j<sfGroup.order.length; j++) {
			let sfName = sfGroup.order[j];
			let sfDef = sfGroup.definitions[sfName];
			let sfDiv = getSmartFilterDiv(sfDef);
			sfDiv.attr('full-name',sfSource+'.'+sfName);
			sfContent.append(sfDiv);
		}
	}
	qbContent = $(getEl('div'))
		.attr('id','vprop-qb');
	vPropContent.append(qbContent);
	qbContent.append($(getEl('p')).text('Use the query builder to create a set of filter rules'));
	let qbDiv = makeFilterGroupDiv({}, 'advanced');
	qbDiv.attr('id','qb-root');
	qbContent.append(qbDiv);
	vPropSel.val('sf');
	vPropSel.change();
	// Load controls
	let loadControls = $(getEl('div'));
	rightDiv.append(loadControls);
	let filterCount = $(getEl('button'))
		.attr('id', 'sf-apply-btn')
		.append('Count')
		.click(function(e) {
			makeSmartfilterJson();
			infomgr.count(dbPath, 'variant', (msg, data) => {
				refreshFilterCounts(data.n);
			})
		});
	loadControls.append(filterCount);
	let countDisplay = $(getEl('div'))
		.attr('id','filter-count-display');
	loadControls.append(countDisplay);
	let filterApply = $(getEl('button'))
		.attr('id', 'sf-apply-btn')
		.append('Apply filter')
		.click(function(evt) {
			var infoReset = resetTab['info'];
			resetTab = {'info': infoReset};
			showSpinner('filter', document.body);
			makeSmartfilterJson(); //TODO: this, better
			loadData(false, null);
		});
	loadControls.append(filterApply);
}

function refreshFilterCounts(n) {
	let t = infomgr.jobinfo['Number of unique input variants']; //TODO is this really the best way to do this?
	let countDisplay = $('#filter-count-display');
	countDisplay.text(`${n} of ${t} variants`);
}

function vPropOptionClick(event) {
	let target = $(event.target);
	let val = target.attr('value');
	let vPropSel = $('#vprop-sel');
	if (val !== vPropSel.val()) {
		vPropSel.val(val);
		vPropSel.change()
	}
	$('.vprop-option').removeClass('active');
	target.addClass('active');
}

function vPropSelectChange(event) {
	let sel = $(event.target);
	let val = sel.val();
	if (val === 'qb') {
		var toShow = $('#vprop-qb');
		var toHide = $('#vprop-sf');
	} else if (val === 'sf') {
		var toShow = $('#vprop-sf');
		var toHide = $('#vprop-qb');
	}
	toShow.css('display','');
	toHide.css('display','none');
}

function onGeneListSelectorChange(event) {
	let target = $(event.target);
	let id = target.attr('id');
	if (id === 'gene-list-text') {
		let textArea = target;
		let fileInput = $('#gene-list-file');
		fileInput.val('');
	} else if (id === 'gene-list-file') {
		let fileInput = target;
		let textArea = $('#gene-list-text');
		let fr = new FileReader();
		fr.onloadend = (event) => {
			textArea.val(event.target.result)
		}
		fr.readAsText(fileInput.prop('files')[0])
	}
}

function onSampleSelectorClick(event) {
	let sbox = $(this);
	let sid = sbox.text();
	if (sbox.hasClass('sample-neutral')) { // Set to require
		sbox.removeClass('sample-neutral');
		sbox.addClass('sample-require');
		sbox.attr('title',`${sid}\nVariants MUST be in this sample`);
	} else if (sbox.hasClass('sample-require')) { // Set to reject
		sbox.removeClass('sample-require');
		sbox.addClass('sample-reject');
		sbox.attr('title',`${sid}\nVariants MUST NOT be in this sample`);
	} else if (sbox.hasClass('sample-reject')) { // Set to neutral
		sbox.removeClass('sample-reject');
		sbox.addClass('sample-neutral');
		sbox.attr('title',sid);
	}
}

function sfCheckboxChangeHandler (event) {
	let cb = $(event.target);
	let sfDiv = cb.closest('.smartfilter');
	let sfActive = cb.prop('checked');
	setSfState(sfDiv, sfActive);
}

function setSfState (sfDiv, active) {
	if (active) {
		sfDiv.removeClass('smartfilter-inactive');
		sfDiv.addClass('smartfilter-active');
		sfDiv.find('.smartfilter-checkbox').prop('checked', true);
	} else {
		sfDiv.addClass('smartfilter-inactive');
		sfDiv.removeClass('smartfilter-active');
		sfDiv.find('.smartfilter-checkbox').prop('checked', false);
	}
}

function getSmartFilterDiv (sfDef) {
	let outerDiv = $(getEl('div'))
		.addClass('smartfilter');
	outerDiv[0].addEventListener('click', e => {
		let sfDiv = $(e.currentTarget);
		if (sfDiv.hasClass('smartfilter-inactive')) {
			setSfState(sfDiv, true);
		}
	}, true)
	let activeCb = $(getEl('input'))
		.attr('type','checkbox')
		.addClass('smartfilter-checkbox')
		.change(sfCheckboxChangeHandler);
	outerDiv.append(activeCb);
	let titleSpan = $(getEl('span'))
		.attr('title', sfDef.description)
		.addClass('sf-title')
		.append(sfDef.title);
	outerDiv.append(titleSpan);
	let defaultValue = sfDef.defaultValue;
	if (defaultValue === undefined || defaultValue === null) {
		defaultValue = '';
	}
	let selectorSpan = $(getEl('span'))
		.addClass('sf-selector');
	outerDiv.append(selectorSpan);
	let selectorType = sfDef.selector.type;
	if (selectorType === 'inputFloat') {
		let defaultValue = sfDef.selector.defaultValue;
		if (defaultValue === undefined || defaultValue === null) {
			defaultValue = 0.0;
		}
		let valueInput = $(getEl('input'))
			.val(defaultValue);
		selectorSpan.append(valueInput);
	} else if (selectorType === 'select') {
		let select = $(getEl('select'))
		.addClass('filter-value-input')
		let allowMult = sfDef.selector.multiple;
		allowMult = allowMult === undefined ? false : allowMult;
		if (allowMult === true) {
			select.prop('multiple','multiple');
		}
		selectorSpan.append(select);
		let options = sfDef.selector.options;
		if (options !== undefined) {
			if (Array.isArray(options)) {
				var optionTexts = options;
				var text2Val = {};
			} else {
				var text2Val = options;
				var optionTexts = Object.keys(text2Val);
			}
		} else {
			let optsColName = sfDef.selector.optionsColumn;
			let optsCol = getFilterColByName(optsColName);
			var optionTexts = optsCol.filter.options;
			var text2Val = {};
			let reportSubs = optsCol.reportsub;
			if (reportSubs !== undefined && Object.keys(reportSubs).length > 0) {
				text2Val = swapJson(reportSubs);
			}
		}
		if (Object.keys(text2Val).length === 0) {
			for (let i=0; i<optionTexts.length; i++) {
				text2Val[optionTexts[i]] = optionTexts[i];
			}
		}
		let defaultValue = sfDef.selector.defaultValue;
		let defaultSelections = [];
		if (defaultValue === undefined || defaultValue === null) {
			defaultSelections = [];
		} else if (Array.isArray(defaultValue)) {
			defaultSelections = defaultValue;
		} else {
			defaultSelections = [defaultValue];

		}
		for (let i=0; i<optionTexts.length; i++) {
			let optText = optionTexts[i];
			let optVal = text2Val[optText];
			let opt = $(getEl('option'))
			.val(optVal)
			.prop('typedValue', optVal)
			.append(optText);
			if (defaultSelections.indexOf(optVal) >= 0) {
				opt[0].selected = true;
			}
			select.append(opt)
		}
		select.pqSelect({
			checkbox: true, 
			displayText: '{0} selected',
			singlePlaceholder: '&#x25BD;',
			multiplePlaceholder: '&#x25BD;',
			maxDisplay: 0,
			width: 200,
			search: false,
			selectallText: 'Select all',
		});
		activeCb.change();
	}
	setSfState(outerDiv, false);
	return outerDiv;
}

function sfOverlayClickHandler (event) {
	let overlay = $(event.target);
	let sfDiv = overlay.closest('.smartfilter');
	sfDiv.addClass('smartfilter-active');
	let cb = sfDiv.children('.smartfilter-checkbox')
	cb.prop('checked',true);
}

function makeSmartfilterJson () {
	let fjs = {}
	// Samples
	let sampleSelectors = $('#sample-select-cont').children();
	fjs.sample = {'require':[],'reject':[]}
	for (let i=0; i<sampleSelectors.length; i++) {
		let sel = $(sampleSelectors[i]);
		if (sel.hasClass('sample-require')) {
			fjs.sample.require.push(sel.text());
		} else if (sel.hasClass('sample-reject')) {
			fjs.sample.reject.push(sel.text());
		}
	}
	// Gene list
	let geneListString = $('#gene-list-text').val();
	let geneList = []
	if (geneListString.length > 0) {
		geneList = geneListString.split('\n');
	}
	fjs.genes = geneList;
	// Variant Properties
	let activeVprop = $('#vprop-sel').val();
	if (activeVprop === 'sf') {
		let sfWrapDiv = $('#vprop-sf');
		let sfDivs = sfWrapDiv.children('div');
		let fullSf = {operator: 'and', rules:[]}
		for (let i=0; i<sfDivs.length; i++) {
			sfDiv = $(sfDivs[i]);
			if (!sfDiv.hasClass('smartfilter-active')) {
				continue;
			}
			let fullName = sfDiv.attr('full-name');
			let sfSource = fullName.split('.')[0];
			let sfName = fullName.split('.')[1];
			let sfDef = smartFilters[sfSource].definitions[sfName];
			let val = pullSfValue(sfDiv);
			let sfResult = addSfValue(sfDef.filter, val);
			fullSf.rules.push(sfResult);
			fjs.variant = fullSf;
		}
	} else if (activeVprop === 'qb') {
		let qbRoot = $('#qb-root');
		fjs.variant = makeGroupFilter(qbRoot);
	}
	
	filterJson = fjs;
	console.log(filterJson);
}

function addSfValue(topRule, value) {
	topRule = JSON.parse(JSON.stringify(topRule));
	if (topRule.hasOwnProperty('rules')) {
		for (let i=0; i<topRule.rules.length; i++) {
			let subRule = topRule.rules[i];
			topRule.rules[i] = addSfValue(subRule, value);
		}
	} else {
		for (let k in topRule) {
			let v = topRule[k];
			if (v === '${value}') {
				topRule[k] = value;
			}
		}
	}
	return topRule;
}

function reduceSf (topRule, allowPartial) {
	topRule = JSON.parse(JSON.stringify(topRule));
	if (topRule.hasOwnProperty('rules')) {
		let newSubRules = [];
		for (let i=0; i<topRule.rules.length; i++) {
			let subRule = topRule.rules[i];
			let newSubRule = reduceSf(subRule, allowPartial);
			if (newSubRule !== null) {
				if (allowPartial) {
					newSubRules.push(newSubRule);
				} else {
					return null;
				}
			}
		}
		topRule.rules = newSubRules;
		if (topRule.rules.length > 1) {
			return topRule;
		} else if (topRule.rules.length === 1) {
			return topRule.rules[0];
		} else {
			return null;
		}
	} else {
		return getFilterColByName(topRule.column) !== null ? topRule : null;
	}
}

function pullSfValue(selectorDiv) {
	let fullName = selectorDiv.attr('full-name');
	let sfSource = fullName.split('.')[0];
	let sfName = fullName.split('.')[1];
	let sfDef = smartFilters[sfSource].definitions[sfName];
	let selectorType = sfDef.selector.type;
	let selectorWrapper = selectorDiv.children('.sf-selector');
	if (selectorType === 'inputFloat') {
		return parseFloat(selectorWrapper.children('input').val());
	} else if (selectorType === 'select') {
		let selector = selectorWrapper.children('.filter-value-input').first();
		let selOpts = selector[0].selectedOptions;
		if (selector.prop('multiple')) {
			let vals = [];
			for (let i=0; i<selOpts.length; i++) {
				vals.push($(selOpts[i]).prop('typedValue'));
			}
			return vals;
		} else {
			return $(selOpts[0]).prop('typedValue');
		}
	}
}

function changeTableDetailMaxButtonText () {
    var div = document.getElementById('tabledetailmaxbuttondiv');
    var button = document.getElementById('tabledetailmaxbutton');
    if (currentTab != 'variant' && currentTab != 'gene') {
        div.style.display = 'none';
        return;
    } else {
        div.style.display = 'block';
    }
    var stat = tableDetailDivSizes[currentTab]['status'];
    var text = null;
    if (stat == undefined || stat == 'both') {
        text = 'View table';
    } else if (stat == 'tablemax') {
        text = 'View detail pane';
    } else if (stat == 'detailmax') {
        text = 'View table + detail pane';
    }
    button.textContent = text;
}

function changeMenu () {
    if (currentTab == 'variant' || currentTab == 'gene') {
        if (firstLoad == false) {
            turnOnMenu('layout_columns_menu');
            turnOnMenu('layout_widgets_menu');
            populateTableColumnSelectorPanel();
            populateWidgetSelectorPanel();
		}
    } else if (currentTab == 'info') {
		turnOffMenu('layout_columns_menu');
        turnOnMenu('layout_widgets_menu');
        populateWidgetSelectorPanel();
	} else {
		turnOffMenu('layout_columns_menu');
		turnOffMenu('layout_widgets_menu');
	}
    if (shouldResizeScreen[currentTab] != false) {
        resizesTheWindow();
    }
    changeTableDetailMaxButtonText();
}

function makeInfoTab (rightDiv) {
	var tabName = 'info';
	var rightContentDiv = getEl('div');
	rightContentDiv.id = 'rightcontentdiv_' + tabName;
	rightContentDiv.className = 'rightcontentdiv';
	addEl(rightDiv, rightContentDiv);

	// Notice
	var noticeDiv = getEl('div');
	noticeDiv.className = 'infonoticediv';
	noticeDiv.id = 'infonoticediv';
	noticeDiv.textContent = ' ';
	addEl(rightContentDiv, noticeDiv);

	// Info
	var infoDiv = getEl('fieldset');
	infoDiv.id = 'info_div';
	addEl(rightContentDiv, infoDiv);

	// Filter
	var filterDiv = document.getElementById('filterdiv');
	populateLoadDiv('info', filterDiv);

	// Widget Notice
	var wgNoticeDiv = getEl('fieldset');
	wgNoticeDiv.id = 'wgnoticediv';
	wgNoticeDiv.className = 'detailContent';
    wgNoticeDiv.style.display = 'none';
	addEl(infoDiv, wgNoticeDiv);
    if (Object.keys(missingWidgets).length == 0) {
        hideWgnoticediv();
    }

	// Widgets
	var widgetDiv = getEl('div');
	widgetDiv.id = 'detailcontainerdiv_info';
	addEl(rightContentDiv, widgetDiv);
}

function toggleFilterDiv () {
	var filterDiv = document.getElementById('filterdiv');
	var filterButton = document.getElementById('filterbutton');
	var display = filterDiv.style.display;
	if (display == 'none') {
		display = 'block';
		filterButton.style.backgroundColor = 'black';
		filterButton.style.color = '#c5dbdb';
	} else {
		display = 'none';
        if (filterArmed.variant != undefined && (filterArmed.variant.groups.length > 0 || filterArmed.variant.columns.length > 0)) {
            filterButton.style.backgroundColor = 'red';
        } else {
            filterButton.style.backgroundColor = '#c5dbdb';
        }
		filterButton.style.color = 'black';
	}
	filterDiv.style.display = display;
}

function populateSummaryWidgetDiv () {
	var tabName = 'info';
	var outerDiv = document.getElementById('detailcontainerdiv_info');
	var widgetDivs = outerDiv.children;
	var reuseWidgets = true;
	if (widgetDivs.length == 0) {
		reuseWidgets = false;
		$(widgetDiv).packery('destroy');
		emptyElement(outerDiv);
	} else {
		widgetDivs = $(outerDiv).packery('getItemElements');
	}
	var widgetNames = Object.keys(widgetGenerators);
	if (widgetNames.length == 0) {
		return;
	} else {
		var orderNums = Object.keys(detailWidgetOrder[tabName]);
		for (var i = 0; i < orderNums.length; i++) {
			var colGroupKey = detailWidgetOrder[tabName][orderNums[i]];
			if (widgetGenerators[colGroupKey] == undefined) {
				continue;
			}
			var colGroupTitle = infomgr.colgroupkeytotitle[colGroupKey];
			if (colGroupTitle == undefined) {
				colGroupTitle = widgetGenerators[colGroupKey]['name'];
			}
			if (widgetGenerators[colGroupKey][tabName] != undefined && 
				widgetGenerators[colGroupKey][tabName]['function'] != undefined) {
				var generator = widgetGenerators[colGroupKey][tabName];
				var widgetDiv = null;
				var widgetContentDiv = null;
				if (reuseWidgets) {
					widgetDiv = document.getElementById(
							'detailwidget_' + tabName + '_' + widgetName);
					widgetContentDiv = document.getElementById(
						'widgetcontentdiv_' + colGroupKey + '_' + tabName);
					if (generator['donterase'] != true) {
						$(widgetContentDiv).empty();
					}
				} else {
					[widgetDiv, widgetContentDiv] = 
						getDetailWidgetDivs(tabName, colGroupKey, colGroupTitle);
                    generator['variables']['parentdiv'] = widgetContentDiv;
				}
				if (reuseWidgets != true) {
					widgetDiv.clientWidth = generator['width'];
					widgetDiv.clientHeight = generator['height'];
					widgetDiv.style.width = generator['width'] + 'px';
					widgetDiv.style.height = generator['height'] + 'px';
				}
                var outerDiv = document.getElementById('detailcontainerdiv_info');
				addEl(outerDiv, widgetDiv);
                try {
                    drawSummaryWidget(colGroupKey);
                } catch (err) {
                    console.log(err);
                    console.log('### continuing to the next widget ###');
                }
			}
		}
	}
	$outerDiv = $(outerDiv);
	$outerDiv.packery({
		columnWidth: widgetGridSize,
		rowHeight: widgetGridSize
	});
	var $widgets = $($outerDiv.packery('getItemElements'));
	$widgets.draggable({
		grid: [widgetGridSize, widgetGridSize],
		handle: '.detailwidgettitle',
        stop: function (evt, ui) {
            $outerDiv.packery();
            loadedViewerWidgetSettings[currentTab] = undefined;
        },
	}).resizable({
		grid: [widgetGridSize, widgetGridSize],
        autoHide: true,
        handles: 'all',
        start: function (evt, ui) {
            var widgetName = evt.target.getAttribute('widgetkey');
            var generator = widgetGenerators[widgetName][currentTab];
            var v = generator['variables'];
            var parentDiv = v['parentdiv'];
            if (generator['beforeresize'] != undefined) {
                generator['beforeresize']();
            }
        },
        stop: function (evt, ui) {
            var widgetName = evt.target.getAttribute('widgetkey');
            var generator = widgetGenerators[widgetName][currentTab];
            var v = generator['variables'];
            var parentDiv = v['parentdiv'];
            if (generator['confirmonresize'] == true) {
                $(parentDiv).empty();
                var div = getEl('div');
                div.className = 'widget-redraw-confirm';
                var span = getEl('span');
                span.textContent = 'Click to redraw';
                addEl(div, span);
                addEl(parentDiv, div);
                div.addEventListener('click', function () {
                    generator['function']();
                });
            } else if (generator['onresize'] != undefined) {
                $(parentDiv).empty();
                if (resizeTimeout) {
                    clearTimeout(resizeTimeout);
                }
                resizeTimeout = setTimeout(function () {
                    var widgetDiv = parentDiv.parentElement;
                    parentDiv.style.height = (widgetDiv.offsetHeight - 38) + 'px';
                    parentDiv.style.width = (widgetDiv.offsetWidth - 17) + 'px';
                    generator['onresize']();
                }, 100);
            }
            var sEvt = evt;
            var sUi = ui;
            $(sEvt.target.parentElement).packery('fit', sUi.element[0]);
            loadedViewerWidgetSettings[currentTab] = undefined;
        },
	});
	$outerDiv.packery('bindUIDraggableEvents', $widgets);
	var resizeTimeout;
	if (reuseWidgets != true) {
		applyWidgetSetting('info');
	}
}

function onClickTableColumnButton () {
	if (currentTab != 'variant' && currentTab != 'gene') {
		return;
	}
	var button = evt.target;
	var panel = button.parentElement.parentElement.getElementsByClassName('tablecolumnselectorpanel')[0];
	var display = panel.style.display;
	if (display == 'none') {
		display = 'block';
		button.style.backgroundColor = '#999999';
	} else {
		display = 'none';
		button.style.backgroundColor = '#ffffff';
	}
	panel.style.display = display;
}

function onClickTableColumnSaveButton (tabName, evt) {

}

function makeVariantGeneTab (tabName, rightDiv) {
    var tableContainerDiv = null;
    var tableDiv = null;
    var northSouthDraggableDiv = null;
    var cellValueDiv = null;
    var detailDiv = null;
    var detailContainerDiv = null;

	// Table div
    var tableDivId = 'tablediv_' + tabName;
	var tableDiv = document.getElementById(tableDivId);
    if (tableDiv == null) {
        tableDiv = getEl('div');
        tableDiv.id = tableDivId;
        tableDiv.className = 'tablediv';
        addEl(rightDiv, tableDiv);
    } else {
        //$(tableDiv).empty();
    }

	// Drag bar
    var northSouthDraggableDivId = 'dragNorthSouthDiv_' + tabName;
    var northSouthDraggableDiv = document.getElementById(northSouthDraggableDivId);
    if (northSouthDraggableDiv == null) {
        northSouthDraggableDiv = getEl('div');
        northSouthDraggableDiv.id = northSouthDraggableDivId;
        northSouthDraggableDiv.className = 'draggableDiv';
        $(northSouthDraggableDiv).draggable({axis:"y"});
        addEl(rightDiv, northSouthDraggableDiv);
    }

	// Cell value div
    var cellValueDivId = 'cellvaluediv_' + tabName;
    var cellValueDiv = document.getElementById(cellValueDivId);
    if (cellValueDiv == null) {
        cellValueDiv = getEl('div');
        cellValueDiv.id = cellValueDivId;
        cellValueDiv.className = 'cellvaluediv';
        var h = loadedHeightSettings['cellvalue_' + currentTab];
        if (h != undefined) {
            cellValueDiv.style.height = h;
        }
        var input = getEl('textarea');
        input.id = 'cellvaluetext_' + tabName;
        input.setAttribute('readonly', 'true');
        input.rows = '1';
        /*
        $(cellValueDiv).resizable({
            resize: function(event, ui) {
                ui.size.width = ui.originalSize.width;
                resizesTheWindow();
            },
        });
        */
        addEl(cellValueDiv, input);
        var button = getEl('button');
        button.textContent = '+';
        button.addEventListener('click', function (evt) {
            var div = document.getElementById('cellvaluediv_' + currentTab);
            var divHeight = div.offsetHeight;
            divHeight = divHeight + 14;
            div.style.height = divHeight + 'px';
            resizesTheWindow();
        });
        addEl(cellValueDiv, button);
        var button = getEl('button');
        button.textContent = '-';
        button.addEventListener('click', function (evt) {
            var div = document.getElementById('cellvaluediv_' + currentTab);
            var divHeight = div.offsetHeight;
            divHeight = divHeight - 14;
            if (divHeight < 18) {
                divHeight = 18;
            }
            div.style.height = divHeight + 'px';
            resizesTheWindow();
        });
        addEl(cellValueDiv, button);
        addEl(rightDiv, cellValueDiv);
    }

	// Detail div
    var detailDivId = 'detaildiv_' + tabName;
    var detailDiv = document.getElementById(detailDivId);
    if (detailDiv == null) {
        detailDiv = getEl('div');
        detailDiv.id = detailDivId;
        detailDiv.className = 'detaildiv';
        var detailContainerWrapDiv = getEl('div');
        detailContainerWrapDiv.className = 'detailcontainerwrapdiv';
        var h = loadedHeightSettings['detail_' + tabName];
        if (h != undefined) {
            detailDiv.style.height = h;
        }
        addEl(detailDiv, detailContainerWrapDiv);
    }

	// Detail content div
    var detailContainerDivId = 'detailcontainerdiv_' + tabName;
    var detailContainerDiv = document.getElementById(detailContainerDivId);
    if (detailContainerDiv == null) {
        detailContainerDiv = getEl('div');
        detailContainerDiv.id = detailContainerDivId;
        detailContainerDiv.className = 'detailcontainerdiv';
        addEl(detailContainerWrapDiv, detailContainerDiv);
        addEl(rightDiv, detailDiv);
    }
}

function onClickDetailRedraw () {
	var tabName = currentTab;
	var div = document.getElementById('detailcontainerdiv_' + tabName);
	$(div).packery();
}

function onClickDetailReset () {
	var tabName = currentTab;
	var div = document.getElementById('detailcontainerdiv_' + tabName);
	var widgets = div.children;
	for (var i = 0; i < widgets.length; i++) {
		var widget = widgets[i];
		var widgetName = widget.getAttribute('widgetkey');
		var generator = widgetGenerators[widgetName][currentTab];
		widget.style.top = '0px';
		widget.style.left = '0px';
		widget.style.width = generator['width'] + 'px';
		widget.style.height = generator['height'] + 'px';
	}
	$(div).packery();
}

function makeSampleMappingTab (tabName, rightDiv) {
	var tableDiv = getEl('div');
	tableDiv.id = 'tablediv_' + tabName;
	tableDiv.className = 'tablediv';
	addEl(rightDiv, tableDiv);
}

function populateWgNoticeDiv (noWgAnnotModules) {
	var contentDiv = document.getElementById('missing-widgets-div');
	if (Object.keys(noWgAnnotModules).length == 0) {
        $(contentDiv).empty();
		var span = getEl('span');
        span.className = 'detailContent';
        span.textContent = 'None';
        addEl(contentDiv, span);
		return;
    }
    emptyElement(contentDiv);
	var msg = 'Your system does not have viwer widgets for the following annotator results are not installed in the system. ';
	msg += 'If you want to install viewer widgets for them, click the buttons for the annotators.';
	var span = getEl('span');
    span.className = 'detailContent';
	addEl(contentDiv, addEl(span, getTn(msg)));
	addEl(contentDiv, getEl('br'));
	addEl(contentDiv, getEl('br'));
	var div = getEl('div');
	var moduleKeys = Object.keys(noWgAnnotModules);
	for (var i = 0; i < moduleKeys.length; i++) {
		var moduleKey = moduleKeys[i];
		var moduleTitle = noWgAnnotModules[moduleKey];
		var button = getEl('button');
        button.setAttribute('module', moduleKey);
		button.style.marginRight = '20px';
		button.style.marginBottom = '10px';
		button.textContent = moduleTitle;
        button.addEventListener('click', function (evt) {
            installWidgetsForModule(evt.target.getAttribute('module'));
        });
		addEl(div, button);
	}
	addEl(contentDiv, div);
}

function installWidgetsForModule (moduleKey) {
    $.get('/store/installwidgetsformodule', {'name': moduleKey}).done(function () {
        checkWidgets();
    });
}

function populateInfoDiv (infoDiv) {
	// Title
	var legend = getEl('legend');
	legend.className = 'section_header';
	addEl(legend, getTn('Analysis Information\xa0'));
    var btn = getEl('span');
    btn.textContent = '\u2a53';
    btn.style.cursor = 'pointer';
    btn.addEventListener('click', function (evt) {
        var btn = evt.target;
        var contentDiv = btn.parentElement.nextSibling;
        var display = contentDiv.style.display;
        var btnText = null;
        if (display == 'none') {
            display = 'block';
            btnText = '\u2a53';
        } else {
            display = 'none';
            btnText = '\u2a54';
        }
        contentDiv.style.display = display;
        btn.textContent = btnText;
    });
    addEl(legend, btn);
	addEl(infoDiv, legend);

	var keys = Object.keys(infomgr.jobinfo);
	var table = getEl('table');
    table.className = 'summary-jobinfo-table';
	var tbody = getEl('tbody');
	for (var i = 0; i < keys.length; i++) {
		var key = keys[i];
		var val = infomgr.jobinfo[key];
		var tr = getEl('tr');
		var td = getEl('td');
		var span = getEl('span');
		span.className = 'detailHeader';
		addEl(tr, addEl(td, addEl(span, getTn(key))));
		var td = getEl('td');
		var span = getEl('span');
        if (key == 'Number of unique input variants') {
            span.id = 'numberofuniqueinputvariants_span';
        }
		span.className = 'detailContent';
		addEl(tr, addEl(td, addEl(span, getTn(val))));
		addEl(tbody, tr);
	}
    var tr = getEl('tr');
    var td = getEl('td');
    var span = getEl('span');
    span.className = 'detailHeader';
    addEl(span, getTn('Missing widgets'));
    addEl(tr, addEl(td, span));
    var td = getEl('td');
    var div = getEl('div');
    div.id = 'missing-widgets-div';
    addEl(td, div);
    addEl(tr, td);
    addEl(tbody, tr);
	addEl(table, tbody);
	addEl(infoDiv, table);
}

function populateWidgetSelectorPanel () {
	var tabName = currentTab;
	var panelDiv = document.getElementById('widgets_showhide_select_div');
	panelDiv.innerHTML = '';
	panelDiv.style.width = '300px';
	panelDiv.style.maxHeight = '400px';
	panelDiv.style.overflow = 'auto';
    panelDiv.style.cursor = 'auto';

	var button = getEl('button');
	button.style.backgroundColor = 'white';
	button.textContent = 'Redraw';
	button.addEventListener('click', function (evt, ui) {
		onClickDetailRedraw();
	});
	addEl(panelDiv, button);

	var button = getEl('button');
	button.style.backgroundColor = 'white';
	button.textContent = 'Reset';
	button.addEventListener('click', function (evt, ui) {
		onClickDetailReset();
	});
	addEl(panelDiv, button);

	var button = getEl('button');
	button.style.backgroundColor = 'white';
	button.textContent = 'Hide all';
	button.addEventListener('click', function (evt, ui) {
		changeWidgetShowHideAll(false);
	});
	addEl(panelDiv, button);

	var button = getEl('button');
	button.style.backgroundColor = 'white';
	button.textContent = 'Show all';
	button.addEventListener('click', function (evt, ui) {
		changeWidgetShowHideAll(true);
	});
	addEl(panelDiv, button);

	var widgetNames = Object.keys(widgetGenerators);
	for (var i = 0; i < widgetNames.length; i++) {
		var widgetName = widgetNames[i];
        var generator = widgetGenerators[widgetName][tabName];
		if (generator != undefined &&
			generator['function'] != undefined &&
			usedAnnotators[tabName].includes(infomgr.widgetReq[widgetName])) {
			var div = getEl('div');
			div.style.padding = '4px';
			var input = getEl('input');
			input.id = 'widgettogglecheckbox_' + tabName + '_' + widgetName;
			input.type = 'checkbox';
            var vwsT = viewerWidgetSettings[tabName];
            if (vwsT == undefined) {
                vwsT = [];
                viewerWidgetSettings[tabName] = vwsT;
            }
            var vws = getViewerWidgetSettingByWidgetkey(tabName, widgetName);
            if (vws == null) {
                input.checked = true;
            } else {
                var display = vws['display'];
                if (display != 'none') {
                    input.checked = true;
					} else {
						input.checked = false;
					}
				}
				input.setAttribute('widgetname', widgetName);
				input.addEventListener('click', function (evt) {
					onClickWidgetSelectorCheckbox(tabName, evt);
				});
				addEl(div, input);
				var span = getEl('span');
				span.style.cursor = 'auto';
				addEl(span, getTn(infomgr.colgroupkeytotitle[widgetName]));
				addEl(div, span);
				if (generator['variables'] != undefined &&
					generator['variables']['shoulddraw'] == false) {
					input.disabled = 'disabled';
					span.style.color = 'gray';
				}
				addEl(panelDiv, div);
			}
		}
	}
	function onClickWidgetHelpButton (evt, tabName) {
		var widget = evt.target.parentElement.parentElement.parentElement;
		var container = widget.parentElement;
		var widgetName = widget.getAttribute('widgetkey');
		var frame = getEl('iframe');
		frame.id = 'widgethelpdiv';
		frame.src = '/result/widgetfile/wg' + widgetName + '/help.html';
		addEl(document.body, frame);
		frame.onload = function () {
			if (this.contentDocument) {
				var btn = getEl('span');
				btn.textContent = '\u274c';
				btn.style.position = 'fixed';
				btn.style.top = '0';
				btn.style.right = '0';
				btn.style.cursor = 'default';
				btn.addEventListener('click', function (evt) {
					$('#widgethelpdiv').remove();
				});
				addEl(this.contentDocument.body, btn);
			} else {
				$(this).remove();
			}
		};
	}

	function onClickWidgetPinButton (evt, tabName) {
		var widget = evt.target.parentElement.parentElement.parentElement;
		var container = widget.parentElement;
		var button = evt.target;
		var pinned = button.classList.contains('pinned');
		if (pinned) {
			button.classList.remove('pinned');
			button.classList.add('unpinned');
			button.src = '/result/images/pin.png';
			$(container).packery('unstamp', widget);
		} else {
			button.src = '/result/images/pin-2.png';
			button.classList.remove('unpinned');
			button.classList.add('pinned');
			$(container).packery('stamp', widget);
		}
	}

	function onClickWidgetCloseButton (tabName, evt) {
		var widgetName = evt.target.getAttribute('widgetname');
		executeWidgetClose(widgetName, tabName, false);
	}

	function onClickWidgetCameraButton (tabName, evt) {
		var widgetName = evt.target.getAttribute('widgetname');
		saveWidgetContent(widgetName, tabName);
	}

	function executeWidgetClose (widgetName, tabName, repack) {
		showHideWidget(tabName, widgetName, false, repack);
		var button = document.getElementById(
				'widgettogglecheckbox_' + tabName + '_' + widgetName);
		if (button != undefined) {
			button.checked = false;
		}
		onClickDetailRedraw();
	}

	function executeWidgetOpen (widgetName, tabName, repack) {
		showHideWidget(tabName, widgetName, true, repack);
		var button = document.getElementById(
				'widgettogglecheckbox_' + tabName + '_' + widgetName);
		if (button != undefined) {
			button.checked = true;
		}
		onClickDetailRedraw();
	}

	function grayOutWidgetSelect (widgetName, tabName) {
		var button = document.getElementById(
			'widgettogglecheckbox_' + tabName + '_' + widgetName);
		if (button != undefined) {
			button.disabled = 'disabled';
			button.nextSibling.style.color = 'gray';
		}
	}

	function changeWidgetShowHideAll (checked) {
		var tabName = currentTab;
		var div = document.getElementById('detailcontainerdiv_' + tabName);
		var widgets = $(div).packery('getItemElements');
		for (var i = 0; i < widgets.length; i++) {
			var widget = widgets[i];
			var widgetName = widget.getAttribute('widgetkey');
			document.getElementById('widgettogglecheckbox_' + tabName + '_' + widgetName).checked = checked;
			showHideWidget(tabName, widgetName, checked, true)
		}
	}

	function onClickWidgetSelectorCheckbox (tabName, evt) {
		var button = evt.target;
		var checked = button.checked;
		var widgetName = button.getAttribute('widgetname');
		showHideWidget(tabName, widgetName, checked, true)
	}

	function showHideWidget (tabName, widgetName, state, repack) {
		var widget = document.getElementById(
				'detailwidget_' + tabName + '_' + widgetName);
		if (widget == null) {
			return;
		}
		var display = widget.style.display;
		if (state == false && display == 'none') {
			return;
		} else if (state == true && display != 'none') {
			return;
		}
		if (state == false) {
			widget.style.display = 'none';
		} else {
			widget.style.display = 'block';
			if (currentTab == 'info') {
				var dcd = widget.getElementsByClassName('detailcontentdiv')[0];
				if (dcd.innerHTML == '') {
					drawSummaryWidget(widgetName);
				}
			}
		}
		var $detailContainerDiv = $(document.getElementById('detailcontainerdiv_' + tabName));
		if (repack == true) {
			$detailContainerDiv.packery('fit', widget);
			onClickDetailReset();
		}
	}

	function drawSummaryWidgetGivenData (widgetName, widgetContentDiv, generator, data) {
		try {
			if (generator['init'] != undefined) {
				generator['init'](data);
			}
			var shouldDraw = false;
			if (generator['shoulddraw'] != undefined) {
				shouldDraw = generator['shoulddraw']();
			} else {
				shouldDraw = true;
			}
			if (generator['variables'] == undefined) {
				generator['variables'] = {};
			}
			generator['variables']['shoulddraw'] = shouldDraw;
			if (shouldDraw) {
				generator['function'](widgetContentDiv, data);
			} else {
				setTimeout(function () {
					executeWidgetClose(widgetName, 'info');
					grayOutWidgetSelect(widgetName, currentTab);
				}, 500);
			}
		} catch (e) {
			console.log(e);
		}
	}

	function getSpinner () {
		var spinner = getEl('img');
		spinner.src = '/result/images/spinner.gif';
		spinner.style.width = '15px';
		return spinner;
	}

	function drawSummaryWidget (widgetName) {
		var widgetContentDiv = document.getElementById('widgetcontentdiv_' + widgetName + '_info');
		emptyElement(widgetContentDiv);
		var generator = widgetGenerators[widgetName]['info'];
		var callServer = generator['callserver'];
		var data = generator['variables']['data'];
		if (callServer && data == undefined) {
			if (generator['beforecallserver'] != undefined) {
				generator['beforecallserver']();
			}
			var callServerParams = {};
			if (generator['variables']['callserverparams'] != undefined) {
				callServerParams = generator['variables']['callserverparams'];
			}
			var spinner = getSpinner();
			spinner.className = 'widgetspinner';
			addEl(widgetContentDiv, spinner);
			$.ajax({
				url: '/result/runwidget/' + widgetName, 
				data: {dbpath: dbPath, params: JSON.stringify(callServerParams)},
				async: true,
				success: function (response) {
					var widgetContentDiv = document.getElementById('widgetcontentdiv_' + widgetName + '_info');
					var spinner = widgetContentDiv.getElementsByClassName('widgetspinner')[0];
					$(spinner).remove();
					var data = response['data'];
					drawSummaryWidgetGivenData(widgetName, widgetContentDiv, generator, data);
				},
			});
		} else if (callServer && data != undefined) {
			drawSummaryWidgetGivenData(widgetName, widgetContentDiv, generator, data);
		} else {
			drawSummaryWidgetGivenData(widgetName, widgetContentDiv, generator, undefined);
		}
	}

	function setupEvents (tabName) {
		$("#dragNorthSouthDiv_" + tabName).on('dragstop', function(){
			afterDragNSBar(this, tabName);
		});

		$('.ui-icon-circle-triangle-n').on('click', function(){
			minimizeOrMaxmimizeTheDetailsDiv(this, 'minimize');
		});
	}

	function placeDragNSBar (tabName) {
		var dragBar = document.getElementById('dragNorthSouthDiv_' + tabName);
		if (! dragBar) {
			return;
		}
		var tableDiv = document.getElementById('tablediv_' + tabName);
		var tableDivHeight = tableDiv.offsetHeight;
		dragBar.style.top = tableDivHeight + 29;
	}

	function placeCellValueDiv (tabName) {
		var div = document.getElementById('cellvaluediv_' + tabName);
		if (! div) {
			return;
		}
		var tableDiv = document.getElementById('tablediv_' + tabName);
		var tableDivHeight = tableDiv.offsetHeight;
		div.style.top = tableDivHeight + ARBITRARY_HEIGHT_SUBTRACTION - 10;
	}

	function addLeftPanelFieldSet (tabName, parent, fieldSetName) {
		var fieldSet = getEl('fieldset');
		var fieldSetId = fieldSetName.toLowerCase().replace(/ /g, '_');
		fieldSet.id = fieldSetId + '_fieldset_' + tabName;
		fieldSet.style.display = 'block';
		var legend = getEl('legend');
		legend.className = 'toggle_header_' + tabName;
		legend.style.cursor = 'pointer';
		legend.style.fontSize = '14px';
		legend.style.fontWeight = 'bold';
		addEl(legend, getTn(fieldSetName));
		var img = getEl('img');
		img.src = '/result/images/minus.png';
		img.style.width = '11px';
		img.style.height = '11px';
		addEl(legend, img);
		addEl(fieldSet, legend);
		var innerDiv = getEl('div');
		innerDiv.id = fieldSetId + '_innerdiv_' + tabName;
		innerDiv.className = 'collapsible';
		addEl(fieldSet, innerDiv);
		addEl(parent, fieldSet);
	}

	function makeGrid (columns, data, tabName) {
		dataLengths[tabName] = data.length;

		var $tableDiv = $('#tablediv_' + tabName);

		var gridObj = loadGridObject(columns, data, tabName, jobId, 'main');
		if (gridObj == undefined) {
			return;
		}

		gridObj.filterModel = {on: true, header: true, type: 'local'};

		gridObj.headerCellClick = function (evt, ui) {
			var $grid = $grids[tabName];
			var sortModel = $grid.pqGrid('option', 'sortModel');
			if (evt.shiftKey) {
				sortModel.single = false;
			} else {
				sortModel.single = true;
			}
			$grid.pqGrid('option', 'sortModel', sortModel);
		};

		// Creates the grid.
		try {
			$tableDiv.pqGrid('destroy');
		} catch (e) {
		}
		var $grid = $tableDiv.pqGrid(gridObj);
		$grids[tabName] = $grid;
		gridObjs[tabName] = gridObj;

		// Adds the footer.
		var footer = $grid.find('.pq-grid-footer')[0];
		var span = getEl('span');
		span.id = 'footertext_' + tabName;
		var button = getEl('button');
		button.id = 'exportbutton_' + tabName;
		button.onclick = function(event) {
			var a = getEl('a');
			var tsvContent = getExportContent(tabName);
			a.href = window.URL.createObjectURL(
					new Blob([tsvContent], {type: 'text/tsv'}));
			a.download = jobId + '_' + tabName + '.tsv';
			document.body.appendChild(a);
			a.click();
			document.body.removeChild(a);
		};
		addEl(button, getTn('Export'));
		addEl(footer, span);
		addEl(footer, button);
		var lenStr = dataLengths[tabName] + ' total rows';
		document.getElementById('footertext_' + tabName).textContent = lenStr;
	}

	function emptyElement (elem) {
		if (elem == null) {
			return;
		}
		var last = null;
		while (last = elem.lastChild) {
			elem.removeChild(last);
		}
	}

	function getFilterCol (columnKey) {
		for (var i = 0; i < filterCols.length; i++) {
			var colModel = filterCols[i].colModel;
			for (var j = 0; j < colModel.length; j++) {
				var column = colModel[j];
				if (column.col == columnKey) {
					return column;
				}
			}
		}
		return null;
	}

	function getLoadSelectorDiv (tabName) {
		var div = getEl('div');

		// Selector
		var selector = getEl('select');
		selector.id = 'filterselect';
		selector.className = 'inlineselect';
		var option = new Option('Choose a column to filter', 'none');
		selector.options.add(option);
		for (var i = 0; i < filterCols.length; i++) {
			var filterCol = filterCols[i];
			var columnGroupName = filterCol.title;
			var colModel = filterCol.colModel;
			for (var j = 0; j < colModel.length; j++) {
				var column = colModel[j];
				if (column.retfilt == true) {
					option = new Option(column.colgroup + ' | ' + column.title, column.col);
					selector.options.add(option);
				}
			}
		}

		selector.onchange = function (evt) {
			onChangeFilterSelector(null, null, null, null);
		}
		addEl(div, selector);

		// Select detail div
		var selectDetailDiv = getEl('div');
		selectDetailDiv.id = 'selectdetaildiv';
		selectDetailDiv.style.display = 'inline-block';
		addEl(div, selectDetailDiv);

		return div;
	}

	function updateLoadMsgDiv (msg) {
		var msgDiv = document.getElementById('load_innerdiv_msg_info');
		emptyElement(msgDiv);
		addEl(msgDiv, getTn(msg));
	}

	function setFilterSelect (div) {
		var selectDiv = div.parentElement.previousSibling;
		var col = div.getAttribute('col');
		var retfilttype = div.getAttribute('retfilttype');
		var val1 = div.getAttribute('val1');
		var val2 = div.getAttribute('val2');
		var checked = div.getAttribute('checked');
		var select = selectDiv.getElementsByClassName('inlineselect')[0];
		onChangeFilterSelector(col, retfilttype, val1, val2, checked);
	}

	function populateLoadDiv (tabName, filterDiv) {
		// Title
		var legend = getEl('legend');
		legend.className = 'section_header';
		addEl(legend, getTn('Variant Filters'));

		// Save Filter Set button
		var button = getEl('button');
		button.style.marginLeft = '10px';
		button.onclick = function(event) {
			saveFilterSettingAs();
		};
		addEl(button, getTn('Save...'));
		addEl(legend, button);

		// Load Filter Set button
		var button = getEl('button');
		button.style.marginLeft = '10px';
		button.onclick = function(event) {
			var filterDiv = document.getElementById('load_filter_select_div');
			var display = filterDiv.style.display;
			if (display == 'none') {
				filterDiv.style.display = 'block';
				loadFilterSettingAs();
			} else {
				filterDiv.style.display = 'none';
			}
		};
		addEl(button, getTn('Load...'));
		addEl(legend, button);

		// Delete Filter Set button
		var button = getEl('button');
		button.style.marginLeft = '10px';
		button.onclick = function (evt) {
			deleteFilterSettingAs();
		}
		addEl(button, getTn('Delete...'));
		addEl(legend, button);

		// Filter name div
		var div = getEl('div');
		div.id = 'load_filter_select_div';
		div.style.display = 'none';
		div.style.position = 'absolute';
		div.style.left = '198px';
		div.style.padding = '6px';
		div.style.overflow = 'auto';
		div.style.backgroundColor = 'rgb(232, 232, 232)';
		div.style.border = '1px solid black';
		addEl(legend, div);

		addEl(filterDiv, legend);

		// Description
		var div = getEl('div');
		var p = getEl('p');
		p.textContent = 'Add variant filters below. Click "Count" to count the '
					   +'number of variants passing the filter. Click "Update" to '
					   +'apply the filter.'
		addEl(div, p);
		addEl(filterDiv, div);

		// Filter
		var div = getEl('div');
		div.id = 'filterwrapdiv';
		populateFilterWrapDiv(div);
		$(filterDiv).append(div);

		// Message
		var div = getEl('div');
		div.id = prefixLoadDiv + 'msg_' + tabName;
		div.style.height = '20px';
		div.style.fontFamily = 'Verdana';
		div.style.fontSize = '12px';
		addEl(filterDiv, div);

		// Count button
		var button = getEl('button');
		button.id = 'count_button';
		button.onclick = function (evt) {
			makeFilterJson();
			infomgr.count(dbPath, 'variant', function (msg, data) {
				updateLoadMsgDiv(msg);
				var count = data['n'];
				if (count <= NUMVAR_LIMIT && count > 0) {
					enableUpdateButton();
				} else {
					disableUpdateButton();
				}
			});
		}
		button.textContent = 'Count';
		addEl(filterDiv, button);

		// Update button
		var button = getEl('button');
		button.id = 'load_button';
		button.onclick = function(evt) {
			toggleFilterDiv();
			evt.target.disabled = true;
			var infoReset = resetTab['info'];
			resetTab = {'info': infoReset};
			showSpinner(tabName, document.body);
			makeFilterJson();
			loadData(false, null);
		};
		addEl(button, getTn('Update'));
		addEl(filterDiv, button);

		// Close button
		var button = getEl('div');
		button.style.position = 'absolute';
		button.style.top = '2px';
		button.style.right = '4px';
		button.style.fontSize = '20px';
		button.textContent = 'X';
		button.style.cursor = 'default';
		button.addEventListener('click', function (evt) {
			toggleFilterDiv();
		});
		addEl(filterDiv, button);
	}

	function onClickFilterLevelButton (button) {
		var simpleFilterDiv = document.getElementById('filter-root-group-div-simple');
		var advancedFilterDiv = document.getElementById('filter-root-group-div-advanced');
		if (button.classList.contains('filter-level-simple')) {
			button.classList.remove('filter-level-simple');
			button.classList.add('filter-level-advanced');
			simpleFilterDiv.style.display = 'none';
			advancedFilterDiv.style.display = null;
		} else if (button.classList.contains('filter-level-advanced')) {
			button.classList.remove('filter-level-advanced');
			button.classList.add('filter-level-simple');
			simpleFilterDiv.style.display = null;
			advancedFilterDiv.style.display = 'none';
		}
	}

	function populateFilterWrapDiv (div) {
		var button = getEl('span');
		button.className = 'filter-level-button';
		button.addEventListener('click', function (evt) {
			onClickFilterLevelButton(evt.target);
		});
		button.classList.add('filter-level-simple');
		addEl(div, button);
		addEl(div, getEl('br'));
		var filter = undefined;
		var filterSimple = undefined;
		var advancedColumnsPresent = false;
		if (filterJson.hasOwnProperty('variant')) {
			filter = filterJson;
			// Make copy without groups for simple filter
			filterSimple = JSON.parse(JSON.stringify(filter));
			filterSimple.variant.groups = [];
			// Also exclude columns that are only available in advanced
			const topFilterCols = filterSimple.variant.columns;
			const topSimpleCols = []
			for (let i=0; i<topFilterCols.length; i++) {
				let filterCol = topFilterCols[i];
				let colModel = getFilterColByName(filterCol.column);
				if (colModel.filterable) {
					topSimpleCols.push(filterCol)
				} else {
					advancedColumnsPresent = true;
				}
			}
			filterSimple.variant.columns = topSimpleCols;
		}
		var filterRootGroupDivSimple = makeFilterRootGroupDiv(filterSimple, 'filter-root-group-div-simple', 'simple');
		$(div).append(filterRootGroupDivSimple);
		button.classList.remove('filter-level-simple'); // Must toggle to advanced so that advanced filter uses all columns in rules selector
		button.classList.add('filter-level-advanced');
		var filterRootGroupDivAdvanced = makeFilterRootGroupDiv(filter, 'filter-root-group-div-advanced', 'advanced');
		button.classList.remove('filter-level-advanced'); // Toggle back
		button.classList.add('filter-level-simple');
		$(div).append(filterRootGroupDivAdvanced);
		filterRootGroupDivSimple[0].style.display = null;
		filterRootGroupDivAdvanced[0].style.display = 'none';
		if ((filter && filter.variant.groups.length > 0) || advancedColumnsPresent) { // Advanced filter
			filterRootGroupDivSimple[0].style.display = 'none';
			filterRootGroupDivAdvanced[0].style.display = null; // Setting element.style null means inherited css style is used
			button.classList.remove('filter-level-simple');
			button.classList.add('filter-level-advanced');
		}
	}

	function populateTableColumnSelectorPanel () {
		var tabName = currentTab;
		var wholeDiv = document.getElementById('columns_showhide_select_div');
		wholeDiv.innerHTML = '';
		wholeDiv.style.width = '400px';
		wholeDiv.style.height = '400px';
		wholeDiv.style.overflow = 'auto';
		var columnGroupsForTab = infomgr.getColumnGroups(tabName);
		var columnGroupNames = Object.keys(columnGroupsForTab);
		var columns = infomgr.getColumns(tabName);
		for (var i = 0; i < columnGroupNames.length; i++) {
			var colGroupNo = i;
			var columnGroupName = columnGroupNames[i];
			var columnGroupColumnKeys = columnGroupsForTab[columnGroupName];

			// Group div
			var groupDiv = document.createElement('fieldset');
			groupDiv.id = columnGroupPrefix + '_' + tabName + '_' + columnGroupName + '_id';
			groupDiv.className = columnGroupPrefix + '_' + tabName + '_class';
			var legend = getEl('legend');
			legend.style.fontSize = '14px';
			legend.style.fontWeight = 'bold';
			var checkbox = getEl('input');
			checkbox.id = columnGroupPrefix + '_' + tabName + '_' + columnGroupName + '_' + '_checkbox';
			checkbox.type = 'checkbox';
			checkbox.checked = true;
			checkbox.setAttribute('colgroupno', i);
			checkbox.setAttribute('colgroupname', columnGroupName);
			checkbox.addEventListener('change', function (evt, ui) {
				var colGroupName = evt.target.getAttribute('colgroupname');
				var cols = infomgr.getColumnGroups(currentTab)[colGroupName];
				var checkboxes = this.parentElement.parentElement.getElementsByClassName('colcheckbox');
				var checked = this.checked;
				for (var i = 0; i < checkboxes.length; i++) {
					var checkbox = checkboxes[i];
					checkbox.checked = checked;
				}
				updateTableColumns(tabName);
			});
			addEl(legend, checkbox);
			addEl(legend, getTn(columnGroupName));
			addEl(groupDiv, legend);

			// Columns
			var columnsDiv = document.createElement('div');
			for (var columnKeyNo = 0; columnKeyNo < columnGroupColumnKeys.length; 
					columnKeyNo++) {
				var columnKey = columnGroupColumnKeys[columnKeyNo];
				var column = columns[infomgr.getColumnNo(tabName, columnKey)];
				var span = getEl('span');
				span.textContent = '\xA0';
				addEl(columnsDiv, span);
				var checkbox = getEl('input');
				checkbox.id = columnGroupPrefix + '_' + tabName + '_' + columnGroupName + '_' + column.col + '_' + '_checkbox';
				checkbox.className = 'colcheckbox';
				checkbox.type = 'checkbox';
				checkbox.checked = !column.hidden;
				checkbox.setAttribute('colgroupname', columnGroupName);
				checkbox.setAttribute('col', column.col);
				checkbox.setAttribute('colno', columnKeyNo);
				checkbox.addEventListener('change', function (evt, ui) {
					updateTableColumns(tabName);
				});
				addEl(columnsDiv, checkbox);
				var span = document.createElement('span');
				span.textContent = column.title;
				addEl(columnsDiv, span);
				var br = getEl('br');
				addEl(columnsDiv, br);
			}
			addEl(groupDiv, columnsDiv);
			addEl(wholeDiv, groupDiv);
		}
	}

	function updateTableColumns (tabName) {
		var selectorPanel = document.getElementById('columns_showhide_select_div');
		var checkboxes = selectorPanel.getElementsByClassName('colcheckbox');
		var colModel = $grids[tabName].pqGrid('option', 'colModel');
		for (var i = 0; i < checkboxes.length; i++) {
			var checkbox = checkboxes[i];
			var colgroupname = checkbox.getAttribute('colgroupname');
			var colkey = checkbox.getAttribute('col');
			var colno = checkbox.getAttribute('colno');
			var checked =  ! checkbox.checked;
			for (var j = 0; j < colModel.length; j++) {
				var cols = colModel[j].colModel;
				for (var k = 0; k < cols.length; k++) {
					var col = cols[k];
					if (col.colgroup == colgroupname && col.col == colkey) {
						cols[k].hidden = checked;
						break;
					}
				}
			}
		}
		$grids[tabName].pqGrid('option', 'colModel', colModel).pqGrid('refresh');
	}
	function showSpinner (tabName, elem) {
		spinner = getEl('img');
		spinner.src = '/result/images/spinner.gif';
		spinner.style.width = '15px';
		addEl(elem.parentElement, spinner);
	}

	function pickThroughAndChangeCursorClasses(domElement, classToSkip, 
				classToAdd) {
		   var classNames = domElement.className;
		   var arrayClasses = classNames.split(" ");
		   var newArrayClassNames = [];
		   for(var i=0; i<arrayClasses.length; i++){
			   if (arrayClasses[i] != classToSkip){
				   newArrayClassNames.push(arrayClasses[i]);
			   }
		   }
		   newArrayClassNames.push(classToAdd);
		   domElement.className = newArrayClassNames.join(" ");	
	}

	function loadGridObject(columns, data, tabName, tableTitle, tableType) {
		var rightDiv = null;
		var detailDiv = document.getElementById('detaildiv_' + tabName);
		var dragBar = document.getElementById('dragNorthSouthDiv_' + tabName);
		var rightDiv = document.getElementById('rightdiv_' + tabName);

		if (rightDiv == null) {
			return;
		}

		var rightDivWidth = rightDiv.offsetWidth;
		var rightDivHeight = rightDiv.offsetHeight;
		var dragBarHeight = 0;
		if (dragBar) {
			dragBarHeight = dragBar.offsetHeight;
		}
		var detailDivHeight = 0;
		if (detailDiv) {
			if (loadedHeightSettings['detail_' + tabName] == undefined) {
				if (rightDivHeight < 660) {
					detailDivHeight = 250;
				} else {
					detailDivHeight = detailDiv.offsetHeight;
				}
			} else {
				detailDivHeight = Number(loadedHeightSettings['detail_' + tabName].replace('px', ''));
			}
			detailDiv.style.height = detailDivHeight + 'px';
		}

		var gridObject = new Object();
		gridObject.title = tableTitle;
		gridObject.width = rightDivWidth;
		gridObject.height = rightDivHeight - dragBarHeight - detailDivHeight - ARBITRARY_HEIGHT_SUBTRACTION - 15;
		gridObject.virtualX = true;
		gridObject.virtualY = true;
		gridObject.wrap = false;
		gridObject.hwrap = true;
		gridObject.sortable = true;
		gridObject.numberCell = {show: false};
		gridObject.showTitle = false;
		gridObject.selectionModel = {type: 'cell', mode: 'block'};
		gridObject.hoverMode = 'cell';
		gridObject.colModel = infomgr.getColModel(tabName);
		gridObject.dataModel = {data: Array.from(data)};
		var sortColumnToUse = 'input_line_number';
		gridObject.sortModel = {
				cancel: true, 
				on: true, 
				type: 'local', 
				single: true, 
				number: true, 
				sorter: [{dataIndx: infomgr.getColumnNo(tabName, 
							sortColumnToUse), dir: 'up'}]};
		gridObject.selectChange = function (event, ui) {
			var clickInfo = ui.selection['_areas'][0];
			var rowNo = clickInfo['r1'];
			var colNo = clickInfo['c1'];
			var rowData = $grids[tabName].pqGrid('getData')[rowNo];
			var cellData = rowData[colNo];
			var valueText = null;
			if (cellData == undefined || cellData == '' || cellData == null) {
				valueText = '';
			} else {
				valueText = cellData;
			}
			var celltextel = document.getElementById('cellvaluetext_' + tabName);
			if (celltextel) {
				celltextel.value = valueText;
			}
			if (selectedRowNos[tabName] != undefined) {
				var row = $grids[tabName].pqGrid('getRow', {rowIndxPage: selectedRowNos[tabName]});
				row.css('background-color', 'white');
			}
			var row = $grids[tabName].pqGrid('getRow', {rowIndxPage: rowNo});
			row.css('background-color', '#ffc500');
			if (rowData != undefined) {
				if (selectedRowIds[tabName] == null || selectedRowIds[tabName] != rowData[0]) {
					selectedRowIds[tabName] = rowData[0];
					selectedRowNos[tabName] = rowNo;
					showVariantDetail(rowData, tabName);
				}
			}
		};
		gridObject.beforeSort = function (evt, ui) {
			if (evt.shiftKey) {
				ascendingSort = {};
				for (var i = 0; i < ui.sorter.length; i++) {
					var sorter = ui.sorter[i];
					ascendingSort[sorter.dataIndx] = (sorter.dir == 'up');
				}
			} else {
				ui.sorter = [ui.sorter[ui.sorter.length - 1]];
				gridObject.sortModel.sorter = ui.sorter;
				if (ui.sorter[0] != undefined) {
					var sorter = ui.sorter[0];
					ascendingSort = {};
					ascendingSort[sorter.dataIndx] = (sorter.dir == 'up');
				}
			}
		};
		gridObject.sortDir = 'up';
		gridObject.options = {
				showBottom: true, 
				dragColumns: {enabled: false}
		};
		gridObject.filter = function () {
			this.scrollRow({rowIndxPage: 0});
		};
		gridObject.collapsible = {on: false, toggle: false};
		gridObject.roundCorners = false;
		gridObject.stripeRows = true;
		gridObject.cellDblClick = function (evt, ui) {
		}
		gridObject.columnOrder = function (evt, ui) {
		}
		gridObject.refresh = function (evt, ui) {
			var selRowNo = selectedRowNos[tabName];
			if (selRowNo >= ui.initV && selRowNo <= ui.finalV) {
				var row = $grids[tabName].pqGrid('getRow', {rowIndxPage: selRowNo});
				row.css('background-color', '#ffc500');
			}
		}
		gridObject.refreshHeader = function (evt, ui) {
			var colModel = null;
			if ($grids[currentTab] == undefined) {
				colModel = this.colModel;
			} else {
				colModel = $grids[currentTab].pqGrid('getColModel');
			}
			var $groupHeaderTr = null;
			var groupHeaderTitleToKey = {};
			for (let i=0; i < colModel.length; i++) {
				var col = colModel[i];
				var $headerCell = this.getCellHeader({colIndx: col.leftPos});
				if ($headerCell.length == 0) {
					continue;
				}
				if (col.desc !== null) {
					$headerCell.attr('title', col.desc).tooltip();
				}
				$groupHeaderTr = $headerCell.parent().prev();
				$headerCell.attr('col', col.col);
				$headerCell.attr('colgroup', col.colgroup);
				groupHeaderTitleToKey[col.colgroup] = col.colgroupkey;
				$headerCell.contextmenu(function (evt) {
					var headerCell = evt.target;
					if (headerCell.classList.contains('pq-td-div')) {
						headerCell = headerCell.parentElement;
					}
					var col = headerCell.getAttribute('col');
					var colgroup = headerCell.getAttribute('colgroup');
					makeTableHeaderRightClickMenu(evt, col, colgroup);
					return false;
				});
			}
			var $groupHeaderTds = $groupHeaderTr.children();
			for (var i = 0; i < $groupHeaderTds.length; i++) {
				var th = $groupHeaderTds[i];
				var title = $(th).children('div').text();
				th.setAttribute('colgrouptitle', title);
				$(th).contextmenu(function (evt) {
					var th = evt.target;
					if (th.tagName == 'DIV') {
						th = th.parentElement;
					}
					var title = th.getAttribute('colgrouptitle');
					makeTableGroupHeaderRightClickMenu(evt, th, title);
					return false;
				});
			}
		}
		gridObject.columnDrag = function (evt, ui) {
			var colGroups = $grids[currentTab].pqGrid('option', 'colModel');
			var colLevel = null;
			if (ui.column.parent == undefined) {
				colLevel = 'group';
			} else {
				colLevel = 'column';
			}
			var uiColGroup = ui.column.colgroup;
			for (var i = 0; i < colGroups.length; i++) {
				var colGroup = colGroups[i];
				var sameColGroup = (uiColGroup == colGroup.pqtitle);
				if (colLevel == 'column') {
					colGroup.nodrop = true;
				} else if (colLevel == 'group') {
					colGroup.nodrop = false;
				}
				var cols = colGroup.colModel;
				for (var j = 0; j < cols.length; j++) {
					var col = cols[j];
					if (colLevel == 'group') {
						col.nodrop = true;
					} else if (colLevel == 'column') {
						if (sameColGroup) {
							col.nodrop = false;
						} else {
							col.nodrop = true;
						}
					}
				}
			}
		}
		gridObject.flex = {on: true, all: false};
		return gridObject;
	}

	function makeTableGroupHeaderRightClickMenu (evt, td, colgrouptitle) {
		var rightDiv = document.getElementById('tablediv_' + currentTab);
		var divId = 'table-header-contextmenu-' + currentTab;
		var div = document.getElementById(divId);
		if (div == undefined) {
			div = getEl('div');
			div.id = divId;
			div.className = 'table-header-contextmenu-div';
		} else {
			$(div).empty();
		}
		div.style.top = evt.pageY;
		div.style.left = evt.pageX;
		var ul = getEl('ul');
		var li = getEl('li');
		var a = getEl('a');
		a.textContent = 'Hide all columns under ' + colgrouptitle;
		li.addEventListener('click', function (evt) {
			var checkboxId = 'columngroup__' + currentTab + '_' + colgrouptitle + '__checkbox';
			var checkbox = document.getElementById(checkboxId);
			checkbox.click();
			div.style.display = 'none';
		});
		addEl(ul, addEl(li, a));
		addEl(div, ul);
		div.style.display = 'block';
		addEl(rightDiv, div);
	}

	function makeTableHeaderRightClickMenu (evt, col, colgroup) {
		var rightDiv = document.getElementById('tablediv_' + currentTab);
		var divId = 'table-header-contextmenu-' + currentTab;
		var div = document.getElementById(divId);
		if (div == undefined) {
			div = getEl('div');
			div.id = divId;
			div.className = 'table-header-contextmenu-div';
		} else {
			$(div).empty();
		}
		div.style.top = evt.pageY;
		div.style.left = evt.pageX;
		var ul = getEl('ul');
		var li = getEl('li');
		var a = getEl('a');
		a.textContent = 'Hide column';
		li.addEventListener('click', function (evt) {
			var checkboxId = 'columngroup__' + currentTab + '_' + colgroup + '_' + col + '__checkbox';
			var checkbox = document.getElementById(checkboxId);
			checkbox.click();
			div.style.display = 'none';
		});
		addEl(ul, addEl(li, a));
		addEl(div, ul);
		div.style.display = 'block';
		addEl(rightDiv, div);
	}

	function applyTableDetailDivSizes () {
		var tabName = currentTab;
		var tableDiv = document.getElementById('tablediv_' + tabName);
		var detailDiv = document.getElementById('detaildiv_' + tabName);
		var detailContainerDiv = document.getElementById('detailcontainerdiv_' + tabName);
		var rightDiv = document.getElementById('rightdiv_' + tabName);
		var drag = document.getElementById('dragNorthSouthDiv_' + tabName);
		var cell = document.getElementById('cellvaluediv_' + tabName);
		var stat = tableDetailDivSizes[tabName]['status'];
		var maxHeight = rightDiv.offsetHeight - 10;
		if (stat == 'tablemax') {
			detailDiv.style.display = 'none';
			drag.style.display = 'none';
			cell.style.display = 'none';
			tableDiv.style.display = 'block';
			tableDiv.style.height = maxHeight + 'px';
			$grids[tabName].pqGrid('option', 'height', maxHeight).pqGrid('refresh');
		} else if (stat == 'detailmax') {
			tableDiv.style.display = 'none';
			drag.style.display = 'none';
			cell.style.display = 'none';
			detailDiv.style.display = 'block';
			detailDiv.style.height = maxHeight + 'px';
			detailDiv.style.top = '10px';
			$(detailContainerDiv).packery();
		} else if (stat == 'both') {
			tableDiv.style.display = 'block';
			detailDiv.style.display = 'block';
			drag.style.display = 'block';
			cell.style.display = 'block';
			var tableHeight = tableDetailDivSizes[tabName]['tableheight'];
			var detailHeight = tableDetailDivSizes[tabName]['detailheight'];
			tableDiv.style.height = tableHeight + 'px';
			$grids[tabName].pqGrid('option', 'height', tableHeight).pqGrid('refresh');
			drag.style.top = (tableHeight - 1 + cell.offsetHeight) + 'px';
			cell.style.top = (tableHeight - 9) + 'px';
			detailDiv.style.height = detailHeight + 'px';
			detailDiv.style.top = (tableHeight + cell.offsetHeight + 12) + 'px';
		}
	}

	function onClickTableDetailMinMaxButton () {
		var tabName = currentTab;
		if (tabName != 'variant' && tabName != 'gene') {
			return;
		}
		var tableDiv = document.getElementById('tablediv_' + tabName);
		var detailDiv = document.getElementById('detaildiv_' + tabName);
		var detailContainerDiv = document.getElementById('detailcontainerdiv_' + tabName);
		var rightDiv = document.getElementById('rightdiv_' + tabName);
		var drag = document.getElementById('dragNorthSouthDiv_' + tabName);
		var cell = document.getElementById('cellvaluediv_' + tabName);
		if (tableDetailDivSizes[tabName] == undefined) {
			tableDetailDivSizes[tabName] = {'status': 'both'};
		}
		var stat = tableDetailDivSizes[tabName]['status'];
		if (stat == 'both') {
			tableDetailDivSizes[tabName]['tableheight'] = tableDiv.offsetHeight;
			tableDetailDivSizes[tabName]['detailheight'] = detailDiv.offsetHeight;
		}
		if (stat == 'both') {
			stat = 'tablemax';
		} else if (stat == 'tablemax') {
			stat = 'detailmax';
		} else if (stat == 'detailmax') {
			stat = 'both';
		}
		tableDetailDivSizes[tabName]['status'] = stat;
		applyTableDetailDivSizes();
		changeTableDetailMaxButtonText();
	}

	function saveWidgetContent (widgetName, tabName) {
		var loadingDiv = drawingWidgetCaptureSpinnerDiv();
		var div = document.getElementById('widgetcontentdiv_' + widgetName + '_' + tabName);
        var divToCapture = div;
        if (divToCapture.childNodes.length == 1) {
            divToCapture = divToCapture.childNodes[0];
        }
        var divW = div.scrollWidth;
        var divH = div.scrollHeight;
        // Table rows are taller than original somehow.
        var trs = div.getElementsByTagName('tr');
        if (trs.length > 0) {
            divH = divH * 3;
        }
        if (divW < divToCapture.scrollWidth) {
            divW = divToCapture.scrollWidth;
        }
        // 7480 is 1000 dpi double-column pixel size from 
        // https://www.elsevier.com/authors/author-schemas/artwork-and-media-instructions/artwork-sizing
        var maxWorH = 7480; 
        var ratioW = maxWorH / divW;
        var ratioH = maxWorH / divH;
        var minRatio = Math.min(ratioW, ratioH);
		domtoimage.toSvg(
				divToCapture, 
				{'width': divW, 'height': divH}).then(function (response) {
					var img = new Image();
					img.src = response;
					img.onload = function () {
						var canvas = getEl('canvas');
						canvas.width = divW * minRatio;
						canvas.height = divH * minRatio;
						ctx = canvas.getContext('2d');
						ctx.scale(minRatio, minRatio);
						ctx.clearRect(0, 0, canvas.width, canvas.height);
						ctx.drawImage(img, 0, 0);
						var dataUrl = canvas.toDataURL('image/png');
						download(dataUrl, jobId + '_' + tabName + '_' + widgetName + '.png', 'image/png');
						loadingDiv.parentNode.removeChild(loadingDiv);
				};
	});
}
