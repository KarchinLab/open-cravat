function updateFilter (tabName) {
	var filterObject = [];
	$('#filter_innerdiv_' + tabName).find('.filtertext').each(function() {
		var $this = $(this);
		var colName = $this.attr('colName');
		var condition = $this.attr('condition');
		var value = this.value;
		var columnnos = infomgr.getColumnNos(tabName);
		filterObject.push({dataIndx: columnnos[colName], condition: condition, value: value});
	});
	$('#filter_innerdiv_' + tabName).find('.filtercheckbox').each(function() {
		var $this = $(this);
		var colName = $this.attr('colName');
		var condition = $this.attr('condition');
		var value = $this.attr('value');
		var columnnos = infomgr.getColumnNos(tabName);
		if (this.checked == true) {
			filterObject.push({dataIndx: columnnos[colName], condition: condition, value: value});
		}
	});
	if ($grids.hasOwnProperty(tabName)) {
		var $grid = $grids[tabName];
		$grid.pqGrid('filter', {
			oper: 'replace',
			data: filterObject
		});
		var numRows = $grid.pqGrid('option', 'dataModel').data.length;
		var lenStr = numRows + ' out of ' + dataLengths[tabName];
		if (tabName == 'gene') {
			lenStr += ' genes';
		} else {
			lenStr += ' variants';
		}
		document.getElementById('footertext_' + tabName).textContent = lenStr;
	}
};

function getClinVarXrefInsert (text) {
	var toks = text.split(';').join(',').split(',');
	var insert = getEl('div');
	insert.style.display = 'inline-block';
	
	for (var i = 0; i < toks.length; i++) {
		var tok = toks[i];
		var toks2 = tok.split(':');
		var source = toks2[0];
		var entry = toks2[1];
		var div = getEl('div');
		div.style.display = 'inline-block';
		addEl(div, getTn(source + ':'));
		var link = null;
		if (source == 'OMIM') {
			link = getEl('a');
			link.href = 'http://omim.org/entry/' + entry;
			link.target = '_blank';
			link.style.color = 'red';
			addEl(link, getTn(entry));
		} else if (source == 'MedGen') {
			link = getEl('a');
			link.href = 'http://www.ncbi.nlm.nih.gov/medgen/' + entry;
			link.target = '_blank';
			link.style.color = 'red';
			addEl(link, getTn(entry));
		} else if (source == 'SNOMED CT') {
			link = getEl('a');
			link.href = 'http://www.snomedbrowser.com/Codes/Details/' + entry;
			link.target = '_blank';
			link.style.color = 'red';
			addEl(link, getTn(entry));
		} else if (source == 'ORPHA' || source == 'Orphanet') {
			link = getEl('a');
			link.href = 'http://www.orpha.net/consor/cgi-bin/OC_Exp.php?Expert=' + entry;
			link.target = '_blank';
			link.style.color = 'red';
			addEl(link, getTn(entry));
		} else if (source == 'Gene') {
			link = getEl('a');
			link.href = 'http://www.ncbi.nlm.nih.gov/gene/' + entry;
			link.target = '_blank';
			link.style.color = 'red';
			addEl(link, getTn(entry));
		} else if (source == 'GeneTests') {
			link = getEl('a');
			link.href = 'https://www.genetests.org/disorders/?disid=' + entry + '&ps=chld';
			link.target = '_blank';
			link.style.color = 'red';
			addEl(link, getTn(entry));
		} else {
			link = getTn(source);
		}
		addEl(div, link);
		addEl(div, getTn('\xA0'));
		addEl(insert, div);
	}
	
	return insert;
}

function getExportContent (tabName) {
	var conditionDic = {'contain':'contains', 'lte':'less than', 'gte':'greater than'};
	
	// Writes job information.
	var content = '';
	content += '# CRAVAT Report\n';
	content += '# Result database: ' + dbPath + '\n';
	content += '# Report section (tab): ' + tabName + '\n';
	
	// Writes filters.
	content += '# Filters\n';
	for (var i = 0; i < filterSet.length; i++) {
		var filterData = filterSet[i];
		var col = filterData[0];
		var condition = col.filter.condition;
		var value = filterData[1];
		var value2 = filterData[2];
		var filterOn = filterData[3];
		if (filterOn) {
			if (value != '') {
				if (condition in conditionDic) {
					condition = conditionDic[condition];
					content += '#     ' + col.title + ': ' + condition + ' ' + value + '\n';
				} else if (condition == 'between') {
					content += '#     ' + col.title + ': ' + condition + ' ' + value + ' and ' + value2 + '\n';
				} else {
					content += '#     ' + col.title + ': ' + condition + ' ' + value + '\n';
				}
			}
		}
	}
	var colTitles = [];
	var colGroups = $grids[tabName].pqGrid('option', 'colModel');
	for (var colGroupNo = 0; colGroupNo < colGroups.length; colGroupNo++) {
		var colGroup = colGroups[colGroupNo];
		var cols = colGroup.colModel;
		for (var j = 0; j < cols.length; j++) {
			var col = cols[j];
			colTitles.push(col.title);
			var filter = col.filter;
			if (filter != undefined) {
				if (filter.on == true) {
					var condition = filter.condition;
					var value = filter.value;
					var value2 = filter.value2;
					if (value != '') {
						if (condition in conditionDic) {
							condition = conditionDic[condition];
							content += '#     ' + col.title + ': ' + condition + ' ' + value + '\n';
						} else if (condition == 'between') {
							content += '#     ' + col.title + ': ' + condition + ' ' + value + ' and ' + value2 + '\n';
						} else {
							content += '#     ' + col.title + ': ' + condition + ' ' + value + '\n';
						}
					}
				}
			}
		}
	}
	content += '\n';
	
	// Writes data headers.
	content += colTitles[0];
	for (var colNo = 1; colNo < colTitles.length; colNo++) {
		content += '\t' + colTitles[colNo];
	}
	content += '\n';
	
	// Writes data rows.
	var rows = $grids[tabName].pqGrid('option', 'dataModel').data;
	for (var rowNo = 0; rowNo < rows.length; rowNo++) {
		var row = rows[rowNo];
		content += row[0];
		for (var colNo = 1; colNo < row.length; colNo++) {
			var value = row[colNo];
			if (value == null) {
				value = '';
			}
			content += '\t' + value;
		}
		content += '\n';
	}
	return content;
}

function afterDragNSBar (self, tabName) {
	var dragBar = self;
	var height_bar = self.offsetHeight;
	var dragBarTop = self.offsetTop;
	var rightDiv = document.getElementById('rightdiv_' + tabName);
	var tableDiv = document.getElementById('tablediv_' + tabName);
	var detailDiv = document.getElementById('detaildiv_' + tabName);
	var cellValueDiv = document.getElementById('cellvaluediv_' + currentTab);

	var rightDiv_height = rightDiv.offsetHeight;
	var rightDiv_top = rightDiv.offsetTop;
	var dragBarTop_relativeRightDiv = dragBarTop - rightDiv_top - 33;
	var cellValueDivTop = dragBarTop_relativeRightDiv + 11;
	var height_table = dragBarTop_relativeRightDiv + 10;
	var height_detail_div = rightDiv_height - height_table - height_bar - 55;
	
	$grids[tabName].pqGrid('option', 'height', height_table).pqGrid('refresh');
	dragBar.style.top = cellValueDivTop + 24;
	cellValueDiv.style.top = cellValueDivTop;
   
	detailDiv.style.height = height_detail_div;
	var tableMinimized = tableDiv.getAttribute('minimized');
	if (tableMinimized == 'true'){
		$(tableDiv).find('.ui-icon-circle-triangle-s')[0].click();
	}
}


function resizesTheWindow () {
	var pqTable = $grids[currentTab];
	if (pqTable == undefined){
		return;
	}
	var tableDiv = document.getElementById('tablediv_' + currentTab);
	var detailDiv = document.getElementById('detaildiv_' + currentTab);
	var nsDragBar = document.getElementById('dragNorthSouthDiv_' + currentTab);
	var rightDiv = document.getElementById('rightdiv_' + currentTab);
	var cellValueDiv = document.getElementById('cellvaluediv_' + currentTab);
	
	var browserHeight = isNaN(window.innerHeight) ? window.clientHeight : window.innerHeight;
	var nsDragBarHeight = 0;
	if (nsDragBar) {
		nsDragBarHeight = nsDragBar.offsetHeight;
	}
	var cellValueDivHeight = 0;
	if (cellValueDiv) {
		cellValueDivHeight = cellValueDiv.offsetHeight;
	}
	var detailDivHeight = 0;
	if (detailDiv) {
		detailDivHeight = detailDiv.offsetHeight;
	}
	
	var rightDivHeight = browserHeight - 67;
    console.log('rightdiv height=', rightDivHeight);
	var tableDivHeight = rightDivHeight - nsDragBarHeight - cellValueDivHeight - detailDivHeight - 35;
	var tableDivWidth = 'calc(100% - 10px)';
	var cellValueDivTop = tableDivHeight - 2 ;
	var nsDragBarTop = cellValueDivTop + cellValueDivHeight + 6;
	
	rightDiv.style.height = rightDivHeight + 'px';
	tableDiv.style.width = tableDivWidth;
	tableDiv.style.height = tableDivHeight;
	pqTable.pqGrid('option', 'width', tableDivWidth).pqGrid('option', 'height', tableDivHeight - 1).pqGrid('refresh');
	cellValueDiv.style.top = cellValueDivTop + 'px';
	nsDragBar.style.top = nsDragBarTop + 'px';
	if (detailDiv) {
		$(detailDiv.getElementsByClassName('detailcontainerdiv')[0]).packery('shiftLayout');
	}
	
	shouldResizeScreen[currentTab] = false;
	
	onClickDetailRedraw();
}

function getResultLevels () {
	var request = new XMLHttpRequest();
	request.open('GET', '/result/service/getresulttablelevels?dbpath=' + dbPath, false);
	request.send(null);
	resultLevels = JSON.parse(request.responseText);
}

function makeTabHeadTabBody (resultTableLevel) {
	var tabHeadsDiv = document.getElementById('tabheads');
	var body = document.body;
	var span = getEl('div');
	var div = getEl('div');
	span.id = 'tabhead_' + resultTableLevel;
	div.id = 'tab_' + resultTableLevel;
	span.className = 'tabhead ';
	div.className = 'tabcontent ';
	if (resultTableLevel == currentTab) {
		span.className += 'show';
		div.className += 'show';
	} else {
		span.className += 'hide';
		div.className += 'hide';
	}
	var tabTitle = resultTableLevel;
	if (tabTitle == 'info') {
		tabTitle = 'summary';
	}
	span.textContent = tabTitle[0].toUpperCase() + tabTitle.substring(1);
	addEl(tabHeadsDiv, span);
	addEl(body, div);
}

function addTabHeadsAndTabContentDivs () {
	getResultLevels();
	for (var i = 0; i < resultLevels.length; i++) {
		var resultTableLevel = resultLevels[i];
		makeTabHeadTabBody(resultTableLevel);
	}
}

function loadData (alertFlag, finalcallback) {
	makeFilterJson();
	var infoReset = resetTab['info'];
	resetTab = {'info': infoReset};
	resetTab['summary'] = true;
	infomgr.datas = {};
	
	var removeSpinner = function () {
		if (spinner != null) {
			spinner.remove();
		}
		for (var i = 0; i < resultLevels.length; i++) {
			var level = resultLevels[i];
			if (level != 'info') {
				var tab = document.getElementById('tab_' + level);
				tab.innerHTML = '';
			}
		}
		if (alertFlag) {
			alert('Data has been loaded.');
		}
		if (finalcallback) {
			finalcallback();
		}
		unlockTabs();
		populateSummaryWidgetDiv();
		if (currentTab == 'info') {
			changeMenu();
		}
		if (currentTab == 'variant' || currentTab == 'gene') {
			setupTab(currentTab);
		}
	}
	var loadMappingResult = function () {
		if (resultLevels.indexOf('mapping') != -1) {
			infomgr.load(jobId, 'mapping', removeSpinner, null, filterJson);
		} else {
			removeSpinner();
		}
	}
	var loadSampleResult = function () {
		if (resultLevels.indexOf('sample') != -1) {
			infomgr.load(jobId, 'sample', loadMappingResult, null, filterJson);
		} else {
			loadMappingResult();
		}
	}
	var loadGeneResult = function () {
		var numvar = infomgr.getData('variant').length;
		if (numvar > NUMVAR_LIMIT) {
			lockTabs();
			flagNotifyToUseFilter = true;
			if (document.getElementById('infonoticediv')) {
				notifyToUseFilter();
				flagNotifyToUseFilter = false;
			} else {
				flagNotifyToUseFilter = true;
				
			}
			removeSpinner();
			return;
		} else {
			flagNotifyToUseFilter = false;
			unlockTabs();
			if (document.getElementById('infonoticediv')) {
				notifyOfReadyToLoad();
			}
		}
		if (resultLevels.indexOf('gene') != -1) {
			infomgr.load(jobId, 'gene', loadSampleResult, null, filterJson);
		} else {
			loadSampleResult();
		}
	}
	var loadVariantResult = function () {
        function callLoadVariant () {
            var callback = null;
            if (usedAnnotators['gene']) {
                callback = loadGeneResult;
            } else {
                callback = loadSampleResult;
            }
            if (resultLevels.indexOf('variant') != -1) {
                infomgr.load(jobId, 'variant', callback, null, filterJson);
            } else {
                callback();
            }
        }
		if (firstLoad) {
			firstLoad = false;
            infomgr.count(dbPath, 'variant', function (numvar) {
                if (numvar > NUMVAR_LIMIT) {
                    lockTabs();
                    flagNotifyToUseFilter = true;
                    if (document.getElementById('infonoticediv')) {
                        notifyToUseFilter();
                        flagNotifyToUseFilter = false;
                    } else {
                        flagNotifyToUseFilter = true;
                    }
                    removeLoadingDiv();
                    return;
                } else {
                    if (flagNotifyToUseFilter) {
                        notifyOfReadyToLoad();
                        flagNotifyToUseFilter = false;
                    }
                    removeLoadingDiv();
                    callLoadVariant();
                }
            });
		} else {
            callLoadVariant();
        }
	}
	lockTabs();
	loadedFilterJson = filterJson;
    makeFilterJson();
	loadVariantResult();
}

function removeLoadingDiv () {
	if (jobDataLoadingDiv != null) {
		jobDataLoadingDiv.parentElement.removeChild(jobDataLoadingDiv);
		jobDataLoadingDiv = null;
	}
}

function lockTabs () {
	$('#tabheads span').css('pointer-events', 'none').css('opacity', '0.5');
}

function unlockTabs () {
	$('#tabheads span').css('pointer-events', 'auto').css('opacity', '1');
}

function notifyToUseFilter () {
	var div = document.getElementById('infonoticediv');
	div.style.background = 'red';
	div.style.display = 'block';
	div.textContent = 
		'Number of variants exceeds viewer limit (' + NUMVAR_LIMIT + ').' +
		'Click the Filter button to use filters to reduce the number of ' +
		'variants to ' + NUMVAR_LIMIT + ' or less, and click Update to load filtered variants.';
}

function hideWgnoticediv () {
    var div = document.getElementById('wgnoticediv');
    div.style.display = 'none';
}

function notifyOfReadyToLoad () {
	var div = document.getElementById('infonoticediv');
	div.style.background = 'white';
	div.textContent = ' ';
	div.style.display = 'none';
}

function firstLoadData () {
	var infoReset = resetTab['info'];
	resetTab = {'info': infoReset};
	
	var loadWidgets = function () {
		detailWidgetOrder = {'variant': {}, 'gene': {}, 'info': {}};
		$.get('/result/service/widgetlist', {}).done(function (jsonResponseData) {
			writeLogDiv('Widget list loaded');
	    	var widgets = jsonResponseData;
	    	var widgetLoadCount = 0;
	    	for (var i = 0; i < widgets.length; i++) {
	    		var widget = widgets[i];
	    		// removes 'wg'.
	    		var widgetName = widget['name'].substring(2);
	    		var title = widget['title'];
	    		var req = widget['required_annotator'];
	    		infomgr.colgroupkeytotitle[widgetName] = title;
	    		infomgr.widgetReq[widgetName] = req;
	    		$.getScript('/result/widgetfile/' + 'wg' + widgetName + '/wg' + widgetName + '.js', function () {
	    			writeLogDiv(widgetName + ' script loaded');
	    			widgetLoadCount += 1;
	    			if (widgetLoadCount == widgets.length) {
	    				setupTab('info');
                        missingWidgets = {};
	        			if (flagNotifyToUseFilter) {
	        				notifyToUseFilter();
	        				flagNotifyToUseFilter = false;
	        			}
	    			}
	    		});
	    		var requiredAnnotator = widgets[i]['required_annotator'];
	    		if (usedAnnotators['variant'].includes(requiredAnnotator)) {
	    			detailWidgetOrder['variant'][Object.keys(detailWidgetOrder['variant']).length] = widgetName;
	    		}
	    		if (usedAnnotators['gene'] && usedAnnotators['gene'].includes(requiredAnnotator)) {
	    			detailWidgetOrder['gene'][Object.keys(detailWidgetOrder['gene']).length] = widgetName;
	    		}
	    		if (((usedAnnotators['variant'] && usedAnnotators['variant'].includes(requiredAnnotator)) || 
	    			(usedAnnotators['gene'] && usedAnnotators['gene'].includes(requiredAnnotator)))) {
	    			detailWidgetOrder['info'][Object.keys(detailWidgetOrder['info']).length] = widgetName;
	    		}
	    	}
	    });
	}
	var afterLoadDefaultWidgetSetting = function (args) {
		infomgr.load(
			jobId, 
			'info', 
			function () {
				populateInfoDiv(document.getElementById('info_div'));
				checkWidgets();
				loadData(false, showTab('info'));
			}, 
			null, 
			filterJson
		);
	}
	var afterLoadDefaultFilter = function (args) {
		loadLayoutSetting(defaultSaveName, afterLoadDefaultWidgetSetting);
	}
	loadWidgets();
	setupTab('info');
	// TMPCHANGE comment out below line
	loadFilterSetting(defaultSaveName, afterLoadDefaultFilter);
}

function checkWidgets () {
	$.get('/result/service/getnowgannotmodules', {dbpath: dbPath}).done(function (jsonResponseData) {
		var noWgAnnotModules = jsonResponseData;
		populateWgNoticeDiv(noWgAnnotModules);
	});
}

function drawingRetrievingDataDiv (currentTab) {
	var currentTabDiv = document.getElementById('tab_'+currentTab);
	var loadingDiv = getEl('div');
	loadingDiv.style.position = 'absolute';
	loadingDiv.style.textAlign = 'center';
	var loadingTxtDiv = getEl('div');
	addEl(loadingTxtDiv, getTn('Retrieving Data...'));
	loadingTxtDiv.style.fontWeight = 'bold';
	loadingTxtDiv.style.fontSize = '6.0em';
	addEl(loadingDiv, loadingTxtDiv);
	var loadingSpinCircleDiv = getEl('div');
	var loadingSpinCircleImg = getEl('img');
	loadingSpinCircleImg.src = "images/bigSpinner.gif";
	loadingSpinCircleImg.style.width = "300px";
	loadingSpinCircleImg.style.height = "300px";
	addEl(loadingSpinCircleDiv, loadingSpinCircleImg);
	addEl(loadingDiv, loadingSpinCircleDiv);
	addEl(currentTabDiv, loadingDiv);
	loadingDiv.style.top = currentTabDiv.getBoundingClientRect().height/2 - loadingDiv.getBoundingClientRect().height/2;
	loadingDiv.style.left = currentTabDiv.getBoundingClientRect().width/2 - loadingDiv.getBoundingClientRect().width/2;
	jobDataLoadingDiv = loadingDiv;
	return loadingDiv;
}

function getCheckNoRowsMessage (tabName, noRows) {
	var msg = '';
	var maxNoRows = infomgr.getStat(tabName)['maxnorows'];
	if (noRows > maxNoRows) {
		msg = 'You have more variants than CRAVAT Result Viewer can display. ' +
			'Use filters below to reduce the number of variants to load. When ' +
			maxNoRows +
			' or less remain, they can be retrieved with the Load button.';
	} else {
		msg = noRows + ' variants selected. Click Load button to retrieve them.';
	}

	// Turns on/off result load button.
	var loadButton = document.getElementById('load_button');
	if (noRows <= maxNoRows) {
		loadButton.style.visibility = 'visible';
	} else {
		loadButton.style.visibility = 'hidden';
	}
	
	return msg;
}

function makeFilterJson () {
    filterJson = {'variant': makeGroupFilter($('#filter-root-group-div'))};
}

function writeLogDiv (msg) {
	var div = document.getElementById('log_div');
	div.textContent = ' ' + msg + ' ';
	$(div).stop(true, true).css({backgroundColor: "#ff0000"}).animate({backgroundColor: "#ffffff"}, 1000);
}

function turnOffMenu (elemId) {
	document.getElementById(elemId).style.display = 'none';
}

function turnOnMenu (elemId) {
	document.getElementById(elemId).style.display = 'inline-block';
}

function doNothing () {
	alert('saved');
}

function webresult_run () {
    var urlParameters = window.location.search.replace("?", "").replace("%20", " ").split("&");
	for (var i = 0; i < urlParameters.length; i++) {
		var keyValue = urlParameters[i].split('=');
		var key = keyValue[0];
		var value = keyValue[1];
		if (key == 'job_id') {
			jobId = value;
		} else if (key == 'dbpath') {
			dbPath = value;
		} else if (key == 'confpath') {
			confPath = value;
		}
	}
	
	$grids = {};
	gridObjs = {};
	
	document.title = 'CRAVAT: ' + jobId;
	
	addTabHeadsAndTabContentDivs();
	
	currentTab = 'info';
	
    $('#tabheads .tabhead').click(function(event) {
    	var targetTab = "#" + this.id.replace('head', '');
    	var tabName = targetTab.split('_')[1];
    	currentTab = tabName;
    	showTab(tabName);
    	var tab = document.getElementById('tab_' + tabName);
    	if (tab.innerHTML == '') {
    		setupTab(tabName);
    	}
    	var detailContainer = document.getElementById('detailcontainerdiv_' + tabName);
    	if (detailContainer != null && detailContainer.innerHTML == '') {
    		setupTab(tabName);
    	}
    	if (tabName == 'variant' || tabName == 'gene' || tabName == 'info') {
    		$(document.getElementById('detailcontainerdiv_' + tabName)).packery();
    	}
    	
    	changeMenu();
    });
    
    var resizeTimeout = null;
    $(window).resize(function(event) {
    	shouldResizeScreen = {};
        var curWinWidth = window.innerWidth;
        var curWinHeight = window.innerHeight;
        if (curWinWidth != windowWidth || curWinHeight != windowHeight) {
            windowWidth = curWinWidth;
            windowHeight = curWinHeight;
            clearTimeout(resizeTimeout);
            resizeTimeout = setTimeout(function () {
                resizesTheWindow();
            }, 200);
        }
    });
    
    jobDataLoadingDiv = drawingRetrievingDataDiv(currentTab);
    
    window.onbeforeunload = function () {
    	if (autoSaveLayout) {
            saveFilterSetting(defaultFilterName, doNothing);
    		saveLayoutSetting(defaultSaveName, doNothing);
    	}
    }
    
    $.get('/result/service/variantcols', {dbpath: dbPath, confpath: confPath, filter: JSON.stringify(filterJson)}).done(function (jsonResponseData) {
    	filterCols = jsonResponseData['columns']['variant'];
    	usedAnnotators = {};
    	var cols = jsonResponseData['columns']['variant'];
    	usedAnnotators['variant'] = [];
    	usedAnnotators['info'] = [];
    	for (var i = 0; i < cols.length; i++) {
    		var col = cols[i];
    		var annotator = col.colModel[0].colgroupkey;
    		usedAnnotators['variant'].push(annotator);
    		usedAnnotators['info'].push(annotator);
    	}
    	if (jsonResponseData['columns']['gene']) {
	    	var cols = jsonResponseData['columns']['gene'];
	    	usedAnnotators['gene'] = [];
	    	for (var i = 0; i < cols.length; i++) {
	    		var col = cols[i];
	    		var annotator = col.colModel[0].colgroupkey;
	    		usedAnnotators['gene'].push(annotator);
	    		usedAnnotators['info'].push(annotator);
	    	}
    	}
    	firstLoadData();
    });
}
