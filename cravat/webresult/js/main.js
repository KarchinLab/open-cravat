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
    var dragBarTopUpperLimit = 100;
    if (dragBarTop < dragBarTopUpperLimit) {
        dragBarTop = dragBarTopUpperLimit;
    }
    var dragBarTopLowerLimit = rightDiv.offsetHeight - 50;
    if (dragBarTop > dragBarTopLowerLimit) {
        dragBarTop = dragBarTopLowerLimit;
    }
    self.style.top = (dragBarTop - 5) + 'px';
	var rightDiv_height = rightDiv.offsetHeight;
	var rightDivTop = rightDiv.offsetTop;
    var cellValueDivHeight = cellValueDiv.offsetHeight;
	var cellValueDivTop = dragBarTop - cellValueDivHeight - 13;
	var height_table = dragBarTop - rightDivTop - cellValueDivHeight;
	var height_detail_div = rightDiv_height - height_table - height_bar - cellValueDivHeight - 25;
    var detailDivTop = cellValueDivTop + cellValueDivHeight + 8 + 15;
	$grids[tabName].pqGrid('option', 'height', height_table).pqGrid('refresh');
	cellValueDiv.style.top = cellValueDivTop;
    detailDiv.style.top = detailDivTop + 'px';
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
	var rightDivHeight = browserHeight - 67;
    var tableDivHeight = 0;
    if (tableDiv) {
        tableDivHeight = tableDiv.offsetHeight;
        if (tableDivHeight > rightDivHeight - 50) {
            tableDivHeight = rightDivHeight - 50;
        }
    }
	var nsDragBarHeight = 0;
	if (nsDragBar) {
		nsDragBarHeight = nsDragBar.offsetHeight;
	}
	var cellValueDivHeight = 0;
	if (cellValueDiv) {
		cellValueDivHeight = cellValueDiv.offsetHeight;
        if (cellValueDivHeight > rightDivHeight - tableDivHeight - 100) {
            cellValueDivHeight = rightDivHeight - tableDivHeight - 100;
            cellValueDiv.style.height = cellValueDivHeight + 'px';
        }
	}
	var detailDivHeight = 0;
	if (detailDiv) {
		detailDivHeight = detailDiv.offsetHeight;
        if (detailDivHeight > rightDivHeight - 50) {
            detailDivHeight = rightDivHeight - 50;
        }
	}
	//var tableDivHeight = rightDivHeight - nsDragBarHeight - cellValueDivHeight - detailDivHeight - 38;
	var detailDivHeight = rightDivHeight - nsDragBarHeight - cellValueDivHeight - tableDivHeight - 28;
    detailDiv.style.height = detailDivHeight + 'px';
	var tableDivWidth = 'calc(100% - 10px)';
	var cellValueDivTop = tableDivHeight - 9;
	var nsDragBarTop = cellValueDivTop + cellValueDivHeight + 7;
	rightDiv.style.height = rightDivHeight + 'px';
	tableDiv.style.width = tableDivWidth;
	tableDiv.style.height = tableDivHeight;
	pqTable.pqGrid('option', 'width', tableDivWidth).pqGrid('option', 'height', tableDivHeight).pqGrid('refresh');
	cellValueDiv.style.top = cellValueDivTop + 'px';
	nsDragBar.style.top = nsDragBarTop + 'px';
	if (detailDiv) {
        detailDiv.style.top = (nsDragBarTop + 15) + 'px';
		$(detailDiv.getElementsByClassName('detailcontainerdiv')[0]).packery('shiftLayout');
	}
	shouldResizeScreen[currentTab] = false;
	onClickDetailRedraw();
    if (tableDetailDivSizes[currentTab]['status'] == 'detailmax') {
        applyTableDetailDivSizes();
    }
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

function disableUpdateButton () {
    document.getElementById('load_button').disabled = true;
}

function enableUpdateButton () {
    document.getElementById('load_button').disabled = false;
}

function disableUpdateButton () {
    document.getElementById('load_button').disabled = true;
}

function clearVariantGeneTab () {
    var tabs = ['variant', 'gene'];
    for (var i = 0; i < tabs.length; i++) {
        var tab = tabs[i];
        var div = document.getElementById('tab_' + tab);
        div.innerHTML = '';
    }
}

function loadData (alertFlag, finalcallback) {
    disableUpdateButton();
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
        clearVariantGeneTab();
		if (currentTab == 'variant' || currentTab == 'gene') {
			setupTab(currentTab);
            resizesTheWindow();
		}
        setFilterButtonText();
        makeVariantByGene();
        document.getElementById('load_innerdiv_msg_info').textContent = infomgr.datas.variant.length + ' variants meet the criteria.';
        enableUpdateButton();
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
			infomgr.load(jobId, 'gene', removeSpinner, null, filterJson);
		} else {
            removeSpinner();
        }
	}
	var loadVariantResult = function () {
		function callLoadVariant () {
		    var callback = null;
		    if (usedAnnotators['gene']) {
                callback = loadGeneResult;
		    } else {
                callback = removeSpinner;
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
                disableUpdateButton();
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
                        disableUpdateButton();
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
    disableUpdateButton();
	loadVariantResult();
    filterArmed = filterJson;
    var filterButton = document.getElementById('filterbutton');
    if (filterArmed.variant != undefined && (filterArmed.variant.groups.length > 0 || filterArmed.variant.columns.length > 0)) {
        filterButton.style.backgroundColor = 'red';
    } else {
        filterButton.style.backgroundColor = '#c5dbdb';
    }
}

function setFilterButtonText () {
    var tot = infomgr.jobinfo['Number of unique input variants'];
    var cur = infomgr.datas.variant.length;
    var button = document.getElementById('filterbutton');
    if (cur < tot) {
        button.textContent = 'Filtered: ' + cur + '/' + tot;
    } else {
        button.textContent = 'Filter';
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
            widgetInfo = {};
	    	var widgets = jsonResponseData;
	    	var widgetLoadCount = 0;
	    	for (var i = 0; i < widgets.length; i++) {
	    		var widget = widgets[i];
	    		// removes 'wg'.
	    		var widgetName = widget['name'].substring(2);
	    		var title = widget['title'];
	    		var req = widget['required_annotator'];
                widgetInfo[widgetName] = widget;
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
                            var req = infomgr.widgetReq[widgetName];
                            var generator = widgetGenerators[widgetName];
                            for (var j = 0; j < widgetTabs.length; j++) {
                                var widgetTab = widgetTabs[j];
                                if (generator[widgetTab]['variables'] == undefined) {
                                    generator[widgetTab]['variables'] = {};
                                }
                                generator[widgetTab]['variables']['widgetname'] = widgetName;
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
                                if (usedAnnotators[widgetTab].includes(req) && 
                                        generator[widgetTab] != undefined) {
                                    var len = Object.keys(detailWidgetOrder[widgetTab]).length;
                                    detailWidgetOrder[widgetTab][len] = widgetName;
                                }
                            }
                        }
                        var widgetTabs = Object.keys(detailWidgetOrder);
                        for (var k = 0; k < widgetTabs.length; k++) {
                            var widgetTab = widgetTabs[k];
                            if (showcaseWidgets[widgetTab] == undefined) {
                                continue;
                            }
                            var poss = Object.keys(detailWidgetOrder[widgetTab]);
                            for (var i1 = 0; i1 < poss.length - 1; i1++) {
                                var pos1 = poss[i1];
                                for (var i2 = i1 + 1; i2 < poss.length; i2++) {
                                    var pos2 = poss[i2];
                                    var widgetName1 = detailWidgetOrder[widgetTab][pos1];
                                    var showcaseIdx1 = showcaseWidgets[widgetTab].indexOf(widgetName1);
                                    var widgetName2 = detailWidgetOrder[widgetTab][pos2];
                                    var showcaseIdx2 = showcaseWidgets[widgetTab].indexOf(widgetName2);
                                    var changeFlag = false;
                                    if (showcaseIdx2 != -1) {
                                        if (showcaseIdx1 != -1) {
                                            if (showcaseIdx2 < showcaseIdx1) {
                                                changeFlag = true;
                                            }
                                        } else {
                                            changeFlag = true;
                                        }
                                    }
                                    if (changeFlag) {
                                        detailWidgetOrder[widgetTab][pos1] = widgetName2;
                                        detailWidgetOrder[widgetTab][pos2] = widgetName1;
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
    loadingDiv.className = 'data-retrieving-msg-div';
	var loadingTxtDiv = getEl('div');
    loadingTxtDiv.className = 'data-retrieving-msg-div-content';
    var span = getEl('span');
    span.textContent = 'Retrieving Data...';
	addEl(loadingTxtDiv, span);
    addEl(loadingTxtDiv, getEl('br'));
	var loadingSpinCircleDiv = getEl('div');
	var loadingSpinCircleImg = getEl('img');
	loadingSpinCircleImg.src = "images/bigSpinner.gif";
	addEl(loadingTxtDiv, loadingSpinCircleImg);
	addEl(loadingDiv, loadingTxtDiv);
    var dW = document.body.offsetWidth;
    var dH = document.body.offsetHeight;
	loadingDiv.style.top = 0;
	loadingDiv.style.left = 0;
	jobDataLoadingDiv = loadingDiv;
    var parentDiv = document.body;
    addEl(parentDiv, loadingDiv);
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

function writeLogDiv (msg) {
	var div = document.getElementById('log_div');
	div.textContent = ' ' + msg + ' ';
	$(div).stop(true, true).css({backgroundColor: "#ff0000"}).animate({backgroundColor: "#ffffff"}, 1000);
}

function turnOffMenu (elemId) {
	document.getElementById(elemId).style.display = 'none';
}

function turnOnMenu (elemId) {
	document.getElementById(elemId).style.display = 'block';
}

function onClickMenu1 (menu) {
    var submenus = menu.getElementsByClassName('menu2_container');
    for (var i = 0; i < submenus.length; i++) {
        var submenu = submenus[i];
        var d = submenu.style.display;
        if (d == 'block') {
            d = 'none';
        } else {
            d = 'block';
        }
        submenu.style.display = d;
    }
}

function onClickColumnsMenu (evt) {
    hideAllMenu3();
    var div = document.getElementById('columns_showhide_select_div');
    div.style.display = 'block';
    evt.stopPropagation();
}

function onClickWidgetsMenu (evt) {
    hideAllMenu3();
    var div = document.getElementById('widgets_showhide_select_div');
    div.style.display = 'block';
    evt.stopPropagation();
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
    document.addEventListener('click', function (evt) {
        var tableHeaderContextmenuId = 'table-header-contextmenu-' + currentTab;
        if (evt.target.closest(tableHeaderContextmenuId) == null) {
            var div = document.getElementById(tableHeaderContextmenuId);
            if (div != null) {
                div.style.display = 'none';
            }
        }
    });
}
