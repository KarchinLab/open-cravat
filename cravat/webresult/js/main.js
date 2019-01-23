function getExportContent (tabName) {
	var conditionDic = {'contain':'contains', 'lte':'less than', 'gte':'greater than'};
	
	// Writes job information.
	var content = '';
	content += '# CRAVAT Report\n';
	content += '# Result database: ' + dbPath + '\n';
	content += '# Report section (tab): ' + tabName + '\n';
	
	// Writes filters.
	content += '# Filters: ';
    content += JSON.stringify(filterJson) + '\n';

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
	var rightDiv = document.getElementById('rightdiv_' + tabName);
	var tableDiv = document.getElementById('tablediv_' + tabName);
	var detailDiv = document.getElementById('detaildiv_' + tabName);
	var cellValueDiv = document.getElementById('cellvaluediv_' + currentTab);
	var dragBar = self;
	var height_bar = self.offsetHeight;
	var dragBarTop = self.offsetTop;
    var dragBarTopUpperLimit = 0;
    if (dragBarTop < dragBarTopUpperLimit) {
        dragBarTop = dragBarTopUpperLimit;
    }
    var dragBarTopLowerLimit = rightDiv.offsetHeight - 50;
    if (dragBarTop > dragBarTopLowerLimit) {
        dragBarTop = dragBarTopLowerLimit;
    }
	var rightDiv_height = rightDiv.offsetHeight;
	var rightDiv_top = rightDiv.offsetTop;
	var dragBarTop_relativeRightDiv = dragBarTop - rightDiv_top - 33;
	var cellValueDivTop = dragBarTop_relativeRightDiv + 11;
	var height_table = dragBarTop_relativeRightDiv + 10;
	var height_detail_div = rightDiv_height - height_table - height_bar - 55;
	$grids[tabName].pqGrid('option', 'height', height_table).pqGrid('refresh');
	dragBar.style.top = cellValueDivTop + 29;
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
	var tableDivHeight = rightDivHeight - nsDragBarHeight - cellValueDivHeight - detailDivHeight - 35;
	var tableDivWidth = 'calc(100% - 10px)';
	var cellValueDivTop = tableDivHeight - 2 ;
	var nsDragBarTop = cellValueDivTop + cellValueDivHeight + 12;
	
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

function getResultLevels (callback) {
    $.ajax({
        method: 'GET',
        url: '/result/service/getresulttablelevels',
        async: true,
        data: {'dbpath': dbPath},
        success: function (response) {
            resultLevels = response;
            callback();
        },
    });
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
	for (var i = 0; i < resultLevels.length; i++) {
		var resultTableLevel = resultLevels[i];
		makeTabHeadTabBody(resultTableLevel);
        tableDetailDivSizes[resultTableLevel] = {'status': 'both'};
	}
}

function loadData (alertFlag, finalcallback) {
	var infoReset = resetTab['info'];
	resetTab = {'info': infoReset};
	resetTab['summary'] = true;
	infomgr.datas = {};
    var makeVariantByGene = function () {
        if (infomgr.datas.variant != undefined) {
            varByGene = {};
            var variantRows = infomgr.datas.variant;
            var hugoColNo = infomgr.getColumnNo('variant', 'base__hugo');
            for (var i = 0; i < variantRows.length; i++) {
                var row = variantRows[i];
                var hugo = row[hugoColNo];
                if (varByGene[hugo] == undefined) {
                    varByGene[hugo] = [];
                }
                varByGene[hugo].push(i);
            }
        }
    };
	var removeSpinner = function () {
		if (spinner != null) {
			spinner.remove();
		}
        document.getElementById('load_button').disabled = false;
		if (alertFlag) {
			alert('Data has been loaded.');
		}
		if (finalcallback) {
			finalcallback();
		}
		if (currentTab == 'info') {
			changeMenu();
		}
        try {
            populateSummaryWidgetDiv();
        } catch (e) {
            console.log(e);
            console.trace();
        }
		if (currentTab == 'variant' || currentTab == 'gene') {
			setupTab(currentTab);
		}
        makeVariantByGene();
        document.getElementById('load_innerdiv_msg_info').textContent = infomgr.datas.variant.length + ' variants meet the criteria.';
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
            var numvar = Number(infomgr.jobinfo['Number of unique input variants']);
            if (filterJson.length == 0 && numvar > NUMVAR_LIMIT) {
                lockTabs();
                flagNotifyToUseFilter = true;
                if (document.getElementById('infonoticediv')) {
                    notifyToUseFilter();
                    flagNotifyToUseFilter = false;
                } else {
                    flagNotifyToUseFilter = true;
                }
                removeLoadingDiv();
                firstLoad = true;
                return;
            }
            if (filterJson.length != 0) {
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
                if (flagNotifyToUseFilter) {
                    notifyOfReadyToLoad();
                    flagNotifyToUseFilter = false;
                }
                removeLoadingDiv();
                callLoadVariant();
            }
		} else {
		    callLoadVariant();
		}
	}
	lockTabs();
	loadVariantResult();
    filterArmed = filterJson;
    var filterButton = document.getElementById('filterbutton');
    if (filterArmed.variant != undefined && (filterArmed.variant.groups.length > 0 || filterArmed.variant.columns.length > 0)) {
        filterButton.style.backgroundColor = 'red';
    } else {
        filterButton.style.backgroundColor = 'white';
    }
}

function removeLoadingDiv () {
	if (jobDataLoadingDiv != null) {
		jobDataLoadingDiv.parentElement.removeChild(jobDataLoadingDiv);
		jobDataLoadingDiv = null;
	}
}

function lockTabs () {
	$('#tabheads div').css('pointer-events', 'none').css('opacity', '0.5');
}

function unlockTabs () {
	$('#tabheads div').css('pointer-events', 'auto').css('opacity', '1');
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

function getViewerWidgetSettingByWidgetkey (tabName, widgetId) {
    var settings = viewerWidgetSettings[tabName];
    if (settings == undefined) {
        return null;
    }
    for (var i = 0; i < settings.length; i++) {
        if (settings[i].widgetkey == widgetId) {
            return settings[i];
        }
    }
    return null;
}

function firstLoadData () {
	var infoReset = resetTab['info'];
	resetTab = {'info': infoReset};
	var loadWidgets = function () {
		detailWidgetOrder = {'variant': {}, 'gene': {}, 'info': {}};
		$.get('/result/service/widgetlist', {}).done(function (jsonResponseData) {
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
                        // processes widget default_hidden
                        var widgetNames = Object.keys(widgetGenerators);
                        for (var k = 0; k < widgetNames.length; k++) {
                            var widgetName = widgetNames[k];
                            var widgetTabs = Object.keys(widgetGenerators[widgetName]);
                            for (var j = 0; j < widgetTabs.length; j++) {
                                var widgetTab = widgetTabs[j];
                                var dh = widgetGenerators[widgetName][widgetTab]['default_hidden'];
                                if (dh != undefined) {
                                    if (dh == true) {
                                        dh = 'none';
                                    } else {
                                        dh = 'block';
                                    }
                                    if (viewerWidgetSettings[widgetTab] == null) {
                                        viewerWidgetSettings[widgetTab] = [];
                                    }
                                    var vws = getViewerWidgetSettingByWidgetkey(widgetTab, widgetName);
                                    if (vws == null) {
                                        viewerWidgetSettings[widgetTab].push({
                                            'widgetkey': widgetName,
                                            'display': dh});
                                    } else {
                                        if (vws['display'] == '') {
                                            vws['display'] = dh;
                                        }
                                    }
                                }
                            }
                        }
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
		loadLayoutSetting(quickSaveName, afterLoadDefaultWidgetSetting, true);
	}
	loadWidgets();
	setupTab('info');
	loadFilterSetting(quickSaveName, afterLoadDefaultFilter, true);
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
    var filterRootGroupDiv = $('#filter-root-group-div');
    var filter = makeGroupFilter(filterRootGroupDiv);
    filterJson = {'variant': filter};
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

function quicksave () {
    filterJson = filterArmed;
    saveLayoutSetting(quickSaveName);
    saveFilterSetting(quickSaveName, true);
}

function afterGetResultLevels () {
	addTabHeadsAndTabContentDivs();
    lockTabs();
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
    jobDataLoadingDiv = drawingRetrievingDataDiv(currentTab);
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

function webresult_run () {
	var urlParams = new URLSearchParams(window.location.search);
	jobId = urlParams.get('job_id');
	dbPath = urlParams.get('dbpath');
	confPath = urlParams.get('confpath');
	$grids = {};
	gridObjs = {};
	document.title = 'CRAVAT: ' + jobId;
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
    // Chrome won't let you directly set this as window.onbeforeunload = function(){}
	// it wont work on a refresh then.
	function triggerAutosave() {
		if (autoSaveLayout) {
            filterJson = filterArmed;
    		saveLayoutSetting(quickSaveName);
			saveFilterSetting(quickSaveName, true);
    	}
	}
    //window.onbeforeunload = triggerAutosave;
    getResultLevels(afterGetResultLevels);
}
