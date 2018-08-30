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
	} else {
		emptyElement(rightDiv);
	}

	// Populates the right panel.
	var detailDiv = null;
	if (tabName == 'info') {
		makeInfoTab(rightDiv);
	} else if (tabName == 'variant' || tabName == 'gene') {
		makeVariantGeneTab(tabName, rightDiv);
	} else if (tabName == 'sample' || tabName == 'mapping') {
		makeSampleMappingTab(tabName, rightDiv);
	}
	addEl(tabDiv, rightDiv);

	setupEvents(tabName);

	if (tabName != 'info') {
		var stat = infomgr.getStat(tabName);
		var columns = infomgr.getColumns(tabName);
		var data = infomgr.getData(tabName);
		dataLengths[tabName] = data.length;

		makeGrid(columns, data, tabName);
		$grids[tabName].pqGrid('refresh');

		// Selects the first row.
		if (tabName == currentTab) {
			if (stat['rowsreturned'] && stat['norows'] > 0) {
				selectedRowIds[tabName] = null;
				$grids[tabName].pqGrid('setSelection', {rowIndx : 0, colIndx: 0, focus: true});
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

	changeMenu();
}

function changeMenu () {
	if (currentTab == 'variant' || currentTab == 'gene' || currentTab == 'info') {
		if (currentTab == 'variant' || currentTab == 'gene') {
			turnOnMenu('layout_columns_menu');
			populateTableColumnSelectorPanel();
		}
		if (firstLoad == false) {
			turnOnMenu('layout_widgets_menu');
			populateWidgetSelectorPanel();
		}
	} else {
		turnOffMenu('layout_columns_menu');
		turnOffMenu('layout_widgets_menu');
	}
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
	infoDiv.style.display = 'inline-block';
	addEl(rightContentDiv, infoDiv);

	// Filter
	var filterDiv = document.getElementById('filterdiv');
	populateLoadDiv('info', filterDiv);

	// Widget Notice
	var wgNoticeDiv = getEl('fieldset');
	wgNoticeDiv.id = 'wgnoticediv';
    wgNoticeDiv.style.display = 'none';
	addEl(rightContentDiv, wgNoticeDiv);
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
		filterButton.style.color = 'white';
	} else {
		display = 'none';
		filterButton.style.backgroundColor = 'white';
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
		/*
		var el = getEl('p');
		el.textContent = 'No summary wigdet';
		addEl(outerDiv, el);
		*/
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
				}
				if (reuseWidgets != true) {
					widgetDiv.clientWidth = generator['width'];
					widgetDiv.clientHeight = generator['height'];
					widgetDiv.style.width = generator['width'] + 'px';
					widgetDiv.style.height = generator['height'] + 'px';
				}
				addEl(outerDiv, widgetDiv);
				drawSummaryWidget(colGroupKey);
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
	}).resizable({
		grid: [widgetGridSize, widgetGridSize]
	});
	$outerDiv.packery('bindUIDraggableEvents', $widgets);
	var resizeTimeout;
	$widgets.on('resize', function (evt, ui) {
		if (resizeTimeout) {
			clearTimeout(resizeTimeout);
		}
		resizeTimeout = setTimeout(function () {
			$outerDiv.packery('fit', ui.element[0]);
		}, 100);
	});
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
	// Table container div
	var tableContainerDiv = getEl('div');
	tableContainerDiv.id = 'tablecontainerdiv_' + tabName;
	addEl(rightDiv, tableContainerDiv);

	// Table div
	var tableDiv = getEl('div');
	tableDiv.id = 'tablediv_' + tabName;
	tableDiv.className = 'tablediv';
	addEl(tableContainerDiv, tableDiv);

	// Drag bar
	var northSouthDraggableDiv = getEl('div');
	northSouthDraggableDiv.id = 'dragNorthSouthDiv_' + tabName;
	northSouthDraggableDiv.className = 'draggableDiv';
	$(northSouthDraggableDiv).draggable({axis:"y"});
	addEl(rightDiv, northSouthDraggableDiv);

	// Cell value div
	var cellValueDiv = getEl('div');
	cellValueDiv.id = 'cellvaluediv_' + tabName;
	cellValueDiv.className = 'cellvaluediv';
	var input = getEl('input');
	input.id = 'cellvaluetext_' + tabName;
	input.type = 'text';
	input.style.width = '100%';
	addEl(cellValueDiv, input);
	addEl(rightDiv, cellValueDiv);

	// Detail div
	var detailDiv = getEl('div');
	detailDiv.id = 'detaildiv_' + tabName;
	detailDiv.className = 'detaildiv';
	var detailContainerWrapDiv = getEl('div');
	detailContainerWrapDiv.className = 'detailcontainerwrapdiv';
	var heightSetting = loadedHeightSettings['detail_' + tabName];
	if (heightSetting != undefined) {
		detailDiv.style.height = heightSetting;
	}
	addEl(detailDiv, detailContainerWrapDiv);

	// Detail content div
	var detailContainerDiv = getEl('div');
	detailContainerDiv.id = 'detailcontainerdiv_' + tabName;
	detailContainerDiv.className = 'detailcontainerdiv';
	addEl(detailContainerWrapDiv, detailContainerDiv);

	addEl(rightDiv, detailDiv);
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
	var wgNoticeDiv = document.getElementById('wgnoticediv');
	if (Object.keys(noWgAnnotModules).length == 0) {
		wgNoticeDiv.style.display = 'none';
		return;
	} else {
        wgNoticeDiv.style.display = 'block';
    }
    emptyElement(wgNoticeDiv);
	var legend = getEl('legend');
	legend.className = 'section_header';
	addEl(legend, getTn('Missing Widgets'));
	addEl(wgNoticeDiv, legend);
	wgNoticeDiv.className = 'detailContent';
	var msg = 'Your system does not have viwer widgets for the following annotator results are not installed in the system. ';
	msg += 'If you want to install viewer widgets for them, click the buttons for the annotators.';
	var span = getEl('span');
	addEl(wgNoticeDiv, addEl(span, getTn(msg)));
	addEl(wgNoticeDiv, getEl('br'));
	addEl(wgNoticeDiv, getEl('br'));
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
	addEl(wgNoticeDiv, div);
}

function installWidgetsForModule (moduleKey) {
    console.log(moduleKey);
    $.get('/store/installwidgetsformodule', {'name': moduleKey}).done(function () {
        console.log('installed widgets for', moduleKey);
        checkWidgets();
    });
}

function populateInfoDiv (infoDiv) {
	// Title
	var span = getEl('legend');
	span.className = 'section_header';
	addEl(span, getTn('Result Information'));
	addEl(infoDiv, span);

	var keys = Object.keys(infomgr.jobinfo);
	var table = getEl('table');
	var tbody = getEl('tbody');
	for (var i = 0; i < keys.length; i++) {
		var key = keys[i];
		var val = infomgr.jobinfo[key];
		var tr = getEl('tr');
		var td = getEl('td');
		td.style.minWidth = '200px';
		var span = getEl('span');
		span.className = 'detailHeader';
		addEl(tr, addEl(td, addEl(span, getTn(key))));
		var td = getEl('td');
		var span = getEl('span');
		span.className = 'detailContent';
		addEl(tr, addEl(td, addEl(span, getTn(val))));
		addEl(tbody, tr);
	}
	addEl(table, tbody);
	addEl(infoDiv, table);
}

function populateWidgetSelectorPanel () {
	var tabName = currentTab;
	var panelDiv = document.getElementById('widgets_showhide_select_div');
	panelDiv.innerHTML = '';
	panelDiv.style.width = '200px';
	panelDiv.style.maxHeight = '400px';
	panelDiv.style.overflow = 'auto';

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

	var widgetNames = Object.keys(widgetGenerators);
	for (var i = 0; i < widgetNames.length; i++) {
		var widgetName = widgetNames[i];
		if (widgetGenerators[widgetName][tabName] != undefined &&
			widgetGenerators[widgetName][tabName]['function'] != undefined &&
			usedAnnotators[tabName].includes(infomgr.widgetReq[widgetName])) {
			var div = getEl('div');
			div.style.padding = '4px';
			var input = getEl('input');
			input.id = 'widgettogglecheckbox_' + tabName + '_' + widgetName;
			input.type = 'checkbox';
			input.checked = true;
			input.setAttribute('widgetname', widgetName);
			input.addEventListener('click', function (evt) {
				onClickWidgetSelectorCheckbox(tabName, evt);
			});
			addEl(div, input);
			var span = getEl('span');
			addEl(span, getTn(infomgr.colgroupkeytotitle[widgetName]));
			addEl(div, span);
			addEl(panelDiv, div);
		}
	}
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

function pinUnpinWidget (tabName, widgetName, evt) {
	var widget = evt.target.parentElement.parentElement.parentElement;
	var container = widget.parentElement;
	$(container).packery('stamp', widget);
}

function onClickWidgetCloseButton (tabName, evt) {
	var widgetName = evt.target.getAttribute('widgetname');
	showHideWidget(tabName, widgetName, false);
	var button = document.getElementById(
			'widgettogglecheckbox_' + tabName + '_' + widgetName);
	button.checked = false;
}

function onClickWidgetSelectorCheckbox (tabName, evt) {
	var button = evt.target;
	var checked = button.checked;
	var widgetName = button.getAttribute('widgetname');
	showHideWidget(tabName, widgetName, checked)
}

function showHideWidget (tabName, widgetName, state) {
	var widget = document.getElementById(
			'detailwidget_' + tabName + '_' + widgetName);
	if (state == false) {
		widget.style.display = 'none';
	} else {
		widget.style.display = 'block';
	}
	var $detailContainerDiv = $(document.getElementById('detailcontainerdiv_' + tabName));
	$detailContainerDiv.packery('fit', widget);
}

function drawSummaryWidget (widgetName) {
	var widgetContentDiv = document.getElementById('widgetcontentdiv_' + widgetName + '_info');
	emptyElement(widgetContentDiv);
	var generator = widgetGenerators[widgetName]['info'];
	var callServer = generator['callserver'];
	if (callServer) {
		$.get('/result/runwidget/' + widgetName, {dbpath: dbPath}).done(function (response) {
			var data = response['data'];
			if (data == {}) {
			} else {
				generator['function'](widgetContentDiv, data);
			}
		});
	} else {
		generator['function'](widgetContentDiv);
	}
}

function setupEvents (tabName) {
    $("#dragNorthSouthDiv_" + tabName).on('dragstop', function(){
	    afterDragNSBar(this, tabName);
    });

    $('.ui-icon-circle-triangle-n').on('click', function(){
	    minimizeOrMaxmimizeTheDetailsDiv(this, 'minimize');
    });

   $(document).keydown(function(button){
	   switch(button.which){
	   case 27:
		   if (tabName == currentTab){
			   if (document.getElementById("splashMupitBckRound_" + tabName) != null){
				   eraseMuPITPopUp(currentTab);
			   }
		   }
	   }
   });
}

function placeDragNSBar (tabName) {
	var dragBar = document.getElementById('dragNorthSouthDiv_' + tabName);
	if (! dragBar) {
		return;
	}
	var tableDiv = document.getElementById('tablediv_' + tabName);
	var tableDivHeight = tableDiv.offsetHeight;
	dragBar.style.top = tableDivHeight + 25;
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

	// Empties if grid exists.
	if ($grids[tabName] != undefined) {
		$grids[tabName].pqGrid('destroy');
	}

	// Creates the grid.
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

function onChangeFilterSelector (col, retFiltType, val1, val2, checked) {
	var select = document.getElementById('filterselect');
	var selectDetailDiv = document.getElementById('selectdetaildiv');
	var columnKey = null;
	if (col != null) {
		$(select).val(col);
		columnKey = col;
	} else {
		option = select.options[select.selectedIndex];
		columnKey = option.value;
	}
	if (columnKey != 'none') {
		var column = getFilterCol(columnKey);
		emptyElement(selectDetailDiv);

		if (retFiltType == null) {
			retFiltType = column['retfilttype'];
		}

		// Operator
		var operatorStr = '';
		if (retFiltType == 'string') {
			operatorStr = 'contains';
		} else if (retFiltType == 'multisel') {
			operatorStr = 'is one of'
		} else if (retFiltType == 'hasvalue') {
			operatorStr = '';
		} else if (retFiltType == 'regexp') {
			operatorStr = 'contains';
		} else if (retFiltType == '<=') {
			operatorStr = '&le;';
		} else if (retFiltType == '>=') {
			operatorStr = '&ge;';
		} else if (retFiltType == 'between') {
			operatorStr = 'between';
		} else {
			operatorStr = retFiltType;
		}
		addEl(selectDetailDiv, getTn('\xA0\xA0' + operatorStr + '\xA0\xA0'));

		// Value box
		var input1 = {};
		var input2 = {};
		if (retFiltType == '<=' || 
				retFiltType == '>=' || 
				retFiltType == 'string' ||
				retFiltType == 'regexp') {
			input1 = getEl('input');
			input1.type = 'text';
			input1.style.width = '60px';
			addEl(selectDetailDiv, input1);
		} else if (retFiltType == 'hasvalue') {
			input1 = getEl('input');
			input1.type = 'checkbox';
			input1.checked = true;
			addEl(selectDetailDiv, input1);
		} else if (retFiltType == 'multisel') {
			input1 = getEl('select');
			for (var i = 0; i < infomgr.getColumnByName(
					tabName, columnKey)['multiseloptions'].length; i++) {
				var multiselOption = infomgr.getColumnByName(
						tabName, columnKey)['multiseloptions'][i];
				input1.options.add(
						new Option(multiselOption, multiselOption));
			}
			addEl(selectDetailDiv, input1);
		} else if (retFiltType == 'between') {
			input1 = getEl('input');
			input2 = getEl('input');
			input1.type = 'text';
			input2.type = 'text';
			input1.style.width = '60px';
			input2.style.width = '60px';
			addEl(selectDetailDiv, input1);
			addEl(selectDetailDiv, getTn(' - '));
			addEl(selectDetailDiv, input2);
		}

		if (val1 != null || val2 != undefined) {
			input1.value = val1;
		}
		if (val2 != null || val2 != undefined) {
			input2.value = val2;
		}

		// space
		var span = getEl('span');
		addEl(span, getTn('\xa0\xa0'));
		addEl(selectDetailDiv, span);

		// Add button
		var addButton = getEl('button');
		if (col != null) {
			addButton.textContent = 'Update';
		} else {
			addButton.textContent = 'Add';
		}
		addButton.onclick = function (evt) {
			var inputs = evt.target.parentElement.getElementsByTagName('input');
			var input1 = inputs[0];
			var input2 = inputs[1];
			var val1 = input1.value;
			var val2 = undefined;
			if (input2 != undefined) {
				val2 = input2.value;
			}
			addToFilterSet(column, val1, val2, true);
			showFilterSet();
			makeFilterJson();
			infomgr.count(dbPath, 'variant', updateLoadMsgDiv);
		}
		addEl(selectDetailDiv, addButton);
	}
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

function addToFilterSet (column, val1, val2) {
	// last true is checkbox flag.
	var filter = [column, val1, val2, true];
	var filterReplaced = false;
	for (var i = 0; i < filterSet.length; i++) {
		if (filterSet[i][0].col == filter[0].col) {
			filterSet[i] = filter;
			filterReplaced = true;
			break;
		}
	}
	if (filterReplaced == false) {
		filterSet.push(filter);
	}
}

function updateLoadMsgDiv (msg) {
	var msgDiv = document.getElementById('load_innerdiv_msg_info');
	emptyElement(msgDiv);
	addEl(msgDiv, getTn(msg));
}

function showFilterSet () {
	var filterListDiv = document.getElementById('filterlistdiv');
	emptyElement(filterListDiv);
	var needBorder = false;
	for (var i = 0; i < filterSet.length; i++) {
		var div = getEl('div');

		var filter = filterSet[i];
		var column = filter[0];
		var val1 = filter[1];
		var val2 = filter[2];
		var checked = filter[3];
		div.setAttribute('col', column.col);
		div.setAttribute('retfilttype', column.retfilttype);
		div.setAttribute('val1', val1);
		div.setAttribute('val2', val2);
		div.setAttribute('checked', checked);

		// Checkbox
		var c = getEl('input');
		c.type = 'checkbox';
		c.setAttribute('col', column.col);
		c.checked = checked;
		c.addEventListener('change', function (evt, ui) {
			var c = evt.target;
			var checked = c.checked;
			var d = c.parentElement;
			var col = d.getAttribute('col');
			if (checked == false) {
				//removeFromFilterSet(col);
				uncheckFilterSet(col);
			} else {
				/*var column = infomgr.getColumnByName('info', col);
				var var1 = d.getAttribute('val1');
				var var2 = d.getAttribute('val2');
				if (var2 == 'undefined') {
					var2 = undefined;
				}*/
				//addToFilterSet(column, var1, var2);
				checkFilterSet(col);
			}
			makeFilterJson();
			infomgr.count(dbPath, 'variant', updateLoadMsgDiv);
		});
		addEl(div, c);

		// Text
		var title = column.colgroup + ' | ' + column.title;
		var opStr = '';
		var valStr = '';
		var operator = column.retfilttype;
		if (operator == 'regexp') {
			opStr = ' contains ';
			valStr = val1;
		} else if (operator == 'between') {
			opStr = ' between ';
			valStr = val1 + ' and ' + val2;
		}
		var span = getEl('span');
		addEl(span, getTn(title + opStr + valStr + " "));
		span.addEventListener('click', function (evt) {
			setFilterSelect(evt.target.parentElement);
		});
		span.style.cursor = 'pointer';
		addEl(div, span);

		// Remove button
		var x = getEl('button');
		addEl(x, getTn('Remove'));
		x.filter = filter;
		x.addEventListener('click', function (evt, ui) {
			this.parentElement.remove();
			var filter = this.filter;
			removeFromFilterSet(filter[0].col);
			if (filterSet.length == 0) {
				document.getElementById('filterlistdiv').style.border = '0px';
			}
			makeFilterJson();
			infomgr.count(dbPath, 'variant', updateLoadMsgDiv);
		});
		addEl(div, x);
		addEl(filterListDiv, div);
		needBorder = true;
	}
	if (needBorder) {
		filterListDiv.style.border = '1px solid gray';
	} else {
		filterListDiv.style.border = '0px';
	}
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

function removeFromFilterSet (col) {
	for (var i = 0; i < filterSet.length; i++) {
		if (filterSet[i][0].col == col) {
			filterSet.splice(i, 1);
			i--;
			break;
		}
	}
}

function uncheckFilterSet (col) {
	for (var i = 0; i < filterSet.length; i++) {
		if (filterSet[i][0].col == col) {
			filterSet[i][3] = false;
			break;
		}
	}
}

function checkFilterSet (col) {
	for (var i = 0; i < filterSet.length; i++) {
		if (filterSet[i][0].col == col) {
			filterSet[i][3] = true;
			break;
		}
	}
}

function populateLoadDiv (tabName, filterDiv) {
	var tabName = 'info';

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

	// Filter name div
	var div = getEl('div');
	div.id = 'load_filter_select_div';
	div.style.display = 'none';
	div.style.position = 'absolute';
	//div.style.width = '200px';
	//div.style.height = '200px';
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
	var desc = 'Add variant filters using the controls below and ' + 
		'click \'Load Variants\' button to update the tables in all tabs ' +
		'with the variants that meet the criteria of all the filters. '
	addEl(div, addEl(p, getTn(desc)));
	var p = getEl('p');
	var desc = 'Also, this result viewer will load up to 100,000 variants ' +
		'to the memory and show. ';
	addEl(p, getTn(desc));
	var desc = 'Thus, if your result has more than 100,000 ' +
		'variants then you need to narrow down the variants to load with ' +
		'the variant filters.';
	addEl(div, addEl(p, getTn(desc)));
	addEl(filterDiv, div);

	// Selector
	var selectorDiv = getLoadSelectorDiv(tabName);
	addEl(filterDiv, selectorDiv);

	// Filter list
	var filterListDiv = getEl('div');
	filterListDiv.id = 'filterlistdiv';
	filterListDiv.className = 'filterlistdiv';
	addEl(filterDiv, filterListDiv);

	// Message
	var div = getEl('div');
	div.id = prefixLoadDiv + 'msg_' + tabName;
	div.style.height = '20px';
	div.style.fontFamily = 'Verdana';
	div.style.fontSize = '12px';
	addEl(filterDiv, div);

	// Load button
	var button = getEl('button');
	button.id = 'load_button';
	button.onclick = function(event) {
		var infoReset = resetTab['info'];
		resetTab = {'info': infoReset};
		showSpinner(tabName, this);
		loadData(false, null);
        toggleFilterDiv();
	};
	addEl(button, getTn('Update'));
	addEl(filterDiv, button);
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
			checkbox.checked = true;
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
		detailDivHeight = detailDiv.offsetHeight;
	}

	var gridObject = new Object();
	gridObject.title = tableTitle;

	gridObject.width = rightDivWidth;
	/*
	var loadedHeight = loadedHeightSettings[tabName];
	if (loadedHeight != undefined) {
		gridObject.height = parseInt(loadedHeight.substring(0, loadedHeight.length - 1));
	} else {
		gridObject.height = rightDivHeight - dragBarHeight - detailDivHeight - ARBITRARY_HEIGHT_SUBTRACTION - 15;
	}
	*/
	gridObject.height = rightDivHeight - dragBarHeight - detailDivHeight - ARBITRARY_HEIGHT_SUBTRACTION - 15;

	gridObject.virtualX = false;
	gridObject.virtualY = true;
	gridObject.wrap = false;
	gridObject.hwrap = true;
	gridObject.sortable = true;
	gridObject.numberCell = {show: false};
	gridObject.showTitle = false;

	gridObject.selectionModel = {type: 'cell', mode: 'block'};
	gridObject.hoverMode = 'row';
	gridObject.colModel = infomgr.getColModel(tabName);
	gridObject.dataModel = {data: data};
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
	gridObject.collapsible = {on: false};
	gridObject.roundCorners = false;
	gridObject.stripeRows = true;
	gridObject.cellDblClick = function (evt, ui) {
	}
	gridObject.columnOrder = function (evt, ui) {
	}

	return gridObject;
}

function minimizeOrMaxmimizeTheDetailsDiv (minimizeOrMaximizeButton, action) {
    var tableBeingAffected = minimizeOrMaximizeButton.parentElement.parentElement.parentElement.parentElement;
    var idOfTableAffected = tableBeingAffected.id;

    var minimizeAttributeOfTableBeforeClick = tableBeingAffected.getAttribute(
		    "minimized");
    var setMinimizeAttributeOfTableTo = null;
    if (minimizeAttributeOfTableBeforeClick == null) {
	    var minimizeAttribute = document.createAttribute("minimized");
	    setMinimizeAttributeOfTableTo = 'true';
	    minimizeAttribute.value = setMinimizeAttributeOfTableTo;
	    tableBeingAffected.setAttributeNode(minimizeAttribute);
    } else {
	    if (minimizeAttributeOfTableBeforeClick == 'true') {
		    setMinimizeAttributeOfTableTo = 'false';
	    } else {
		    setMinimizeAttributeOfTableTo = 'true';
	    }
	    tableBeingAffected.setAttribute('minimized', 
			    setMinimizeAttributeOfTableTo);
    }

    var tabAffected = idOfTableAffected.split('_')[1];
    var rightDivWithPiecesChanging = null;
    rightDivWithPiecesChanging = document.getElementById(
		    'rightdiv_' + tabAffected);
    var heightRightDivChanging = parseInt(
		    rightDivWithPiecesChanging.offsetHeight, 10);

    var changeHeightOfDetailsDiv = true;

    changeHeightOfDetailsDiv = true;
    if (changeHeightOfDetailsDiv == true){
	    setTimeout(function(){
		    var heightTableNow = parseInt(tableBeingAffected.offsetHeight, 10);
		    var detailDivAffected = document.getElementById(
				    'detaildiv_' + tabAffected);
		    var heightDragBarNS = null;
		    detailDivAffected = document.getElementById(
				    'detaildiv_' + tabAffected);
		    heightDragBarNS = parseInt(document.getElementById(
				    'dragNorthSouthDiv_' + tabAffected).offsetHeight, 10);
		    var newHeightOfDetailDiv = heightRightDivChanging - heightTableNow 
		   			- heightDragBarNS - ARBITRARY_HEIGHT_SUBTRACTION;
		   detailDivAffected.style.height = newHeightOfDetailDiv;
	   }, 400);   
   }
}
