function getExportContent (tabName) {
	var conditionDic = {'contain':'contains', 'lte':'less than', 'gte':'greater than'};
	// Writes job information.
	var content = '';
	content += '# CRAVAT Report\n';
	content += '# Result database: ' + dbPath + '\n';
	content += '# Report section (tab): ' + tabName + '\n';
	// Writes filters.
	content += '# Load filters: ';
    content += JSON.stringify(filterJson) + '\n';
    content += '# Table filters:\n';
	var colTitles = [];
	var colGroups = $grids[tabName].pqGrid('option', 'colModel');
    var colNos = [];
    var colNo = -1;
    var colGroupTitles = [];
    var colGroupNumCols = {};
	for (var colGroupNo = 0; colGroupNo < colGroups.length; colGroupNo++) {
		var colGroup = colGroups[colGroupNo];
		var cols = colGroup.colModel;
        var colExist = false;
        var numCols = 0;
		for (var j = 0; j < cols.length; j++) {
            colNo++;
			var col = cols[j];
            if (col.hidden) {
                continue;
            }
            colExist = true;
            colNos.push(col.dataIndx);
            numCols++;
			colTitles.push(col.title.replace(' ', '_'));
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
                        } else if (col.filter.type == 'select') {
                            content += '#     ' + col.title + ': ' + value + '\n';
						} else {
							content += '#     ' + col.title + ': ' + condition + ' ' + value + '\n';
						}
					}
				}
			}
		}
        if (colExist) {
            var colGroupTitle = colGroup.title.replace(' ', '_');
            colGroupTitles.push(colGroupTitle);
            colGroupNumCols[colGroupTitle] = numCols;
        }
	}
	// Writes data headers.
    if (colGroupTitles.length == 0) {
        return '';
    }
    content += colGroupTitles[0];
    for (var j = 0; j < colGroupNumCols[colGroupTitles[0]]; j++) {
        content += '\t';
    }
    for (var i = 1; i < colGroupTitles.length; i++) {
        var colGroupTitle = colGroupTitles[i];
        content += colGroupTitle;
        var numCols = colGroupNumCols[colGroupTitle];
        for (var j = 0; j < numCols; j++) {
            content += '\t';
        }
    }
    content += '\n';
	content += colTitles[0];
	for (var i = 1; i < colTitles.length; i++) {
		content += '\t' + colTitles[i];
	}
	content += '\n';
	// Writes data rows.
	var rows = $grids[tabName].pqGrid('option', 'dataModel').data;
	for (var rowNo = 0; rowNo < rows.length; rowNo++) {
		var row = rows[rowNo];
        var value = row[colNos[0]];
        if (value == null) {
            value = '';
        }
		content += value;
		for (var i = 1; i < colNos.length; i++) {
			var value = row[colNos[i]];
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
	var rightDivHeight = browserHeight - 70;
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

function showNoDB () {
    var div = getEl('div');
    div.id = 'sorrydiv';
    var img = getEl('img');
    img.src = '/result/images/sorry.png';
    addEl(div, img);
    var span = getEl('p');
    span.style.fontSize = '36px';
    span.textContent = 'Sorry...';
    addEl(div, span);
    var span = getEl('p');
    span.style.fontSize = '20px';
    span.textContent = 'OpenCRAVAT was unable to show the job result.';
    addEl(div, span);
    addEl(div, getEl('br'));
    var span = getEl('p');
    span.style.fontSize = '16px';
    span.textContent = 'Usually, it is because...';
    addEl(div, span);
    addEl(div, getEl('br'));
    var span = getEl('p');
    span.style.fontSize = '16px';
    span.textContent = '\u2022 Job ID is incorrect.'
    addEl(div, span);
    var span = getEl('p');
    span.style.fontSize = '16px';
    span.textContent = '\u2022 You are not authorized to view this job result.';
    addEl(div, span);
    var span = getEl('p');
    span.style.fontSize = '16px';
    span.textContent = '\u2022 Result database path is wrong.';
    addEl(div, span);
    addEl(document.body, div);
}

function getResultLevels (callback) {
    $.ajax({
        method: 'GET',
        url: '/result/service/getresulttablelevels',
        async: true,
        data: {'job_id': jobId, 'username': username, 'dbpath': dbPath},
        success: function (response) {
            if (response.length > 0 && response[0] == 'NODB') {
                showNoDB();
            } else {
                resultLevels = response;
                callback();
            }
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
	span.classList.add('tabhead');
	div.classList.add('tabcontent');
	if (resultTableLevel == currentTab) {
		span.classList.add('show');
		div.classList.add('show');
	} else {
		span.classList.add('hide');
		div.classList.add('hide');
	}
	var tabTitle = resultTableLevel;
	if (tabTitle == 'info') {
		tabTitle = 'summary';
	}
	span.textContent = tabTitle.toUpperCase();
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

function disableUpdateButton ({countHigh=false}={}) {
    var btn = document.getElementById('load_button');
    btn.disabled = true;
}

function enableUpdateButton () {
    var btn = document.getElementById('load_button');
    btn.disabled = false;
    btn.innerText = 'Apply filter';
}

function clearVariantGeneTab () {
    var tabs = ['variant', 'gene'];
    for (var i = 0; i < tabs.length; i++) {
        var tab = tabs[i];
        var div = document.getElementById('tab_' + tab);
        div.innerHTML = '';
    }
}

function iterationCopy (src) {
    var target = {};
    for (var prop in src) {
        if (src.hasOwnProperty(prop)) {
            target[prop] = src[prop];
        }
    }
    return target;
}

function copyColModel (colModelGroup) {
    var newColModelGroup = {};
    newColModelGroup.name = colModelGroup.name;
    newColModelGroup.title = colModelGroup.title;
    var newColModel = [];
    var colModel = colModelGroup.colModel;
    for (var i = 0; i < colModel.length; i++) {
        var col = colModel[i];
        var newcol = {};
        newcol.col = col.col;
        newcol.colgroup = col.colgroup;
        newcol.colgroupkey = col.colgroupkey;
        newcol.title = col.title;
        newcol.align = col.align;
        newcol.dataIndx = col.dataIndx;
        newcol.retfilt = col.retfilt;
        newcol.retfilttype = col.retfilttype;
        newcol.multiseloptions = col.multiseloptions;
        newcol.reportsub = col.reportsub;
        newcol.categories = col.categories;
        newcol.width = col.width;
        newcol.desc = col.desc;
        newcol.type = col.type;
        newcol.hidden = col.hidden;
        newcol.default_hidden = col.default_hidden;
        newcol.ctg = col.ctg;
        newcol.filterable = col.filterable;
        newcol.link_format = col.link_format;
        newcol.filter = col.filter;
        newcol.fromgenelevel = true;
        newcol.render = col.render;
        newColModel.push(newcol);
    }
    newColModelGroup.colModel = newColModel;
    return newColModelGroup;
}

function addGeneLevelToVariantLevel () {
    var oriNoColVar = infomgr.columnss.variant.length;
    // colModel
    var geneColModels = infomgr.colModels['gene'];
    var colNo = oriNoColVar;
    var colgroupsToSkip = [];
    var colsToSkip = [];
    for (var i = 0; i < geneColModels.length; i++) {
        var colModel = geneColModels[i];
        if (colModel.name == 'base' || colModel['genesummary'] == true) {
            colgroupsToSkip.push(colModel.name);
            for (var j = 0; j < colModel.colModel.length; j++) {
                colsToSkip.push(colModel.colModel[j].col);
            }
            continue;
        }
        var colModel = copyColModel(geneColModels[i]);
        /*
        var cols = colModel.colModel;
        for (var j = 0; j < cols.length; j++) {
            cols[j].dataIndx = colNo;
            colNo++;
        }
        */
        infomgr.colModels['variant'].push(colModel);
    }
    // Sorts colModel.
    var vcm = infomgr.colModels['variant'];
    for (var i = 0; i < vcm.length - 1; i++) {
        for (var j = i + 1; j < vcm.length; j++) {
            var cmi = vcm[i];
            var cmj = vcm[j];
            if (cmi.name == 'base' || cmi.name == 'tagsampler') {
                continue;
            }
            if (cmi.title.toLowerCase() > cmj.title.toLowerCase()) {
                var tmp = cmi;
                vcm[i] = cmj;
                vcm[j] = tmp;
            }
        }
    }
    // assigns dataIndx to variant colModels.
    var vcm = infomgr.colModels['variant'];
    var varDataIndx = 0;
    var colNoDict = {};
    var varColumnss = [];
    var varColumngroupss = {};
    var varColumnnoss = {};
    for (var i = 0; i < vcm.length; i++) {
        var varColModel = vcm[i].colModel;
        var varColNames = [];
        for (var j = 0; j < varColModel.length; j++) {
            var varCol = varColModel[j];
            var level = 'variant';
            if (varCol.fromgenelevel == true) {
                level = 'gene';
            }
            colNoDict[varDataIndx] = {'level': level, 'colno': varCol.dataIndx};
            varCol.dataIndx = varDataIndx;
            varColumnnoss[varCol.col] = varDataIndx;
            varDataIndx++;
            varColumnss.push(varCol);
            varColNames.push(varCol.col);
        }
        varColumngroupss[vcm[i].name] = varColNames;
    }
    infomgr.columnss.variant = varColumnss;
    infomgr.columngroupss.variant = varColumngroupss;
    infomgr.columnnoss.variant = varColumnnoss;
    // columngroupss
    /*
    var geneColumnGroups = infomgr.columngroupss.gene;
    var geneColumnGroupNames = Object.keys(geneColumnGroups);
    for (var i = 0; i < geneColumnGroupNames.length; i++) {
        var geneColumnGroupName = geneColumnGroupNames[i];
        if (geneColumnGroupName == 'base' || colgroupsToSkip.indexOf(geneColumnGroupName) >= 0) {
            continue;
        }
        infomgr.columngroupss.variant[geneColumnGroupName] = geneColumnGroups[geneColumnGroupName];
    }
    */
    // columnnoss
    /*
    var geneColumnnos = infomgr.columnnoss.gene;
    var maxColNo = Math.max(...Object.values(infomgr.columnnoss.variant));
    var geneColumnNames = Object.keys(geneColumnnos);
    var colNoDict = {};
    var varColNo = 0;
    var varColumnnoss = {};
    var varColumnss = [];
    var initVarColumnnossKeys = Object.keys(infomgr.columnnoss.variant);
    var initGeneColumnnossKeys = Object.keys(infomgr.columnnoss.gene);
        // infomgr.colModels.variant already has gene level colModels.
    for (var j = 0; j < infomgr.colModels.variant.length; j++) {
        var varColModel = infomgr.colModels.variant[j];
        var varColModelName = varColModel.name;
        var colAdded = false;
        for (var k = 0; k < initVarColumnnossKeys.length; k++) {
            var colkey = initVarColumnnossKeys[k];
            var colgrp = colkey.split('__')[0];
            if (colgrp == varColModelName) {
                varColumnnoss[colgrp] = varColNo;
                varColumnss.push(infomgr.columnss.variant[k]);
                colNoDict[varColNo] = {'level': 'variant', 'colno': k};
                varColNo++;
                colAdded = true;
            }
        }
        // does not add gene column group if variant level already has it.
        if (colAdded) {
            continue;
        }
        for (var k = 0; k < initGeneColumnnossKeys.length; k++) {
            var colkey = initGeneColumnnossKeys[k];
            if (colsToSkip.indexOf(colkey) >= 0) {
                continue;
            }
            var colgrp = colkey.split('__')[0];
            if (colgrp == varColModelName) {
                varColumnnoss[colgrp] = varColNo;
                varColumnss.push(JSON.parse(JSON.stringify(infomgr.columnss.gene[k])));
                colNoDict[varColNo] = {'level': 'gene', 'colno': k};
                varColNo++;
            }
        }
    }
    infomgr.columnnoss.variant = varColumnnoss;
    infomgr.columnss.variant = varColumnss;
    */
    // column default hidden exist
    var vcs = Object.keys(infomgr.colgroupdefaulthiddenexist.variant);
    var gcs = Object.keys(infomgr.colgroupdefaulthiddenexist.gene);
    for (var i = 0; i < gcs.length; i++) {
        var colgrpname = gcs[i];
        if (vcs.indexOf(colgrpname) == -1) {
            infomgr.colgroupdefaulthiddenexist['variant'][colgrpname] = JSON.parse(JSON.stringify(infomgr.colgroupdefaulthiddenexist['gene'][colgrpname]));
        }
    }
    // dataModel
    var geneDataModels = infomgr.datas.gene;
    geneRows = {};
    for (var i = 0; i < geneDataModels.length; i++) {
        var row = geneDataModels[i];
        var hugo = row[0];
        geneRows[hugo] = row;
    }
    var hugoColNo = infomgr.getColumnNo('variant', 'base__hugo');
    function convertToInt (v) {
        return parseInt(v);
    }
    var numCols = Math.max(...Object.keys(colNoDict).map(convertToInt)) + 1;
    for (var varRowNo = 0; varRowNo < infomgr.datas.variant.length; varRowNo++) {
        var varRow = infomgr.datas.variant[varRowNo];
        var hugo = varRow[hugoColNo];
        var geneRow = geneRows[hugo];
        var newRow = [];
        for (var colNo = 0; colNo < numCols; colNo++) {
            var colTo = colNoDict[colNo];
            var level = colTo['level'];
            var colno = colTo['colno'];
            var cell = null;
            if (level == 'variant') {
                cell = infomgr.datas[level][varRowNo][colno];
            } else if (level == 'gene') {
                if (geneRow == undefined) {
                    cell = null;
                } else {
                    cell = geneRow[colno];
                }
            }
            newRow.push(cell);
        }
        infomgr.datas.variant[varRowNo] = newRow;
    }
}

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

function loadData (alertFlag, finalcallback) {
    lockTabs();
	var infoReset = resetTab['info'];
	resetTab = {'info': infoReset};
	resetTab['summary'] = true;
    resetTab['variant'] = true;
    resetTab['gene'] = true;
	infomgr.datas = {};
	var removeSpinner = function () {
        addGeneLevelToVariantLevel();
        makeVariantByGene();
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
        //clearVariantGeneTab();
		if (currentTab == 'variant' || currentTab == 'gene') {
			setupTab(currentTab);
            resizesTheWindow();
		}
        enableUpdateButton();
        unlockTabs();
        if (jobDataLoadingDiv != null) {
            jobDataLoadingDiv.parentElement.removeChild(jobDataLoadingDiv);
            jobDataLoadingDiv = null;
        }
        //selectTab('info');
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
			if (document.getElementById('infonoticediv')) {
				notifyOfReadyToLoad();
			}
		}
		if (resultLevels.indexOf('gene') != -1) {
			infomgr.load(jobId, 'gene', removeSpinner, null, filterJson, 'job');
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
                infomgr.load(jobId, 'variant', callback, null, filterJson, 'job');
		    } else {
                callback();
		    }
		}
		if (firstLoad) {
			firstLoad = false;
            var numvar = Number(infomgr.jobinfo['Number of unique input variants']);
            if (filterJson.length == 0 && numvar > NUMVAR_LIMIT) {
                displayFilterCount(numvar);
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
                	if (numvar.includes('Error')){
                		removeLoadingDiv();
                		alert(numvar);
                	} else if (numvar > NUMVAR_LIMIT) {
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
                        //removeLoadingDiv();
                        callLoadVariant();
                    }
                }, 5);
            } else {
                if (flagNotifyToUseFilter) {
                    notifyOfReadyToLoad();
                    flagNotifyToUseFilter = false;
                }
                //removeLoadingDiv();
                callLoadVariant();
            }
		} else {
		    callLoadVariant();
		}
	}
	lockTabs();
	loadVariantResult();
    filterArmed = filterJson;
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
    $('#tabhead_info').css('pointer-events', 'auto').css('opacity', '1');
}

function unlockTabs () {
	$('#tabheads div').css('pointer-events', 'auto').css('opacity', '1');
}

function notifyToUseFilter () {
	var div = document.getElementById('infonoticediv');
    div.style.background = 'red';
    div.textContent = 
         `The OpenCRAVAT viewer cannot display more than ${NUMVAR_LIMIT} variants. `
        +`Use the filter tab to load at most ${NUMVAR_LIMIT} variants.`;
	showInfonoticediv();
    document.getElementById('tabhead_filter').style.pointerEvents = 'auto';
}

function hideWgnoticediv () {
    var div = document.getElementById('wgnoticediv');
    div.style.display = 'none';
}

function notifyOfReadyToLoad () {
	var div = document.getElementById('infonoticediv');
	div.style.background = 'white';
	div.textContent = '';
	hideInfonoticediv();
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
                            if (widgetTabs.length == 1 && widgetTabs[0] == 'gene') {
                                widgetTabs.unshift('variant');
                            }
                            var req = infomgr.widgetReq[widgetName];
                            var generator = widgetGenerators[widgetName];
                            if (generator['gene'] != undefined && generator['variant'] == undefined) {
                                generator['variant'] = generator['gene'];
                            }
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
	loadWidgets();
	setupTab('info');
	loadFilterSetting(quickSaveName, afterLoadDefaultFilter, true);
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
        filterJson,
        'info'
    );
}

var afterLoadDefaultFilter = function (args) {
    loadLayoutSetting(quickSaveName, afterLoadDefaultWidgetSetting, true);
}

function checkWidgets () {
	$.ajax({
        url: '/result/service/getnowgannotmodules', 
        data: {'username': username, 'job_id': jobId, dbpath: dbPath},
        async: true,
        success: function (jsonResponseData) {
            var noWgAnnotModules = jsonResponseData;
            populateWgNoticeDiv(noWgAnnotModules);
        },
	});
}

function drawingRetrievingDataDiv (currentTab) {
    if (jobDataLoadingDiv == null) {
        var currentTabDiv = document.getElementById('tab_'+currentTab);
        var loadingDiv = getEl('div');
        loadingDiv.className = 'data-retrieving-msg-div';
        var loadingTxtDiv = getEl('div');
        loadingTxtDiv.className = 'store-noconnect-msg-div';
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
    }
	return loadingDiv;
}

function drawingWidgetCaptureSpinnerDiv () {
	var currentTabDiv = document.getElementById('tab_'+currentTab);
	var loadingDiv = getEl('div');
    loadingDiv.className = 'data-retrieving-msg-div';
	var loadingTxtDiv = getEl('div');
    loadingTxtDiv.className = 'store-noconnect-msg-div';
    var span = getEl('span');
    span.textContent = 'Capturing widget content...';
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

function turnOffLayoutMenu () {
    var submenu = document.querySelector('#menu_div .menu1 .menu2_container');
    submenu.classList.add('hide');
    submenu.classList.remove('show-block');
}

function onClickMenu1 (menu) {
    var submenus = menu.getElementsByClassName('menu2_container');
    for (var i = 0; i < submenus.length; i++) {
        var submenu = submenus[i];
        if (submenu.classList.contains('show-block')) {
            submenu.classList.add('hide');
            submenu.classList.remove('show-block');
        } else {
            submenu.classList.remove('hide');
            submenu.classList.add('show-block');
        }
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

function onClickHelpMenu(evt) {
    const helpDiv = document.getElementById('helpdiv');
    if (helpDiv.style.display === 'flex') {
        helpDiv.style.display = 'none';
    } else {
        helpDiv.style.display = 'flex';
    }
    evt.stopPropagation();
}

function quicksave () {
    filterJson = filterArmed;
    saveLayoutSetting(quickSaveName, 'quicksave');
    //saveFilterSetting(quickSaveName, true);
}

function invokePackage () {
	document.getElementById('packageSubmit').style.display = '';
    document.getElementById('helpdiv').style.display = 'none';
}

function cancelPackage () {
	document.getElementById('packageSubmit').style.display = 'none'
}

function saveAndPackage () {
	var packageName = document.getElementById('packageName').value;
	if (packageName === '') {
        var alertDiv = getEl('div');
        var span = getEl('span');
        span.textContent = 'A package was not provided. Please enter a name for this package.'
        addEl(alertDiv, span);
        showYesNoDialog(alertDiv, null, false, true);
        return;
	}
    for (const [key, value] of Object.entries(existingPackages)) {
    	var packageKey = `${key}`
    	if (packageKey === packageName) {
    		matchFound = true;
            var alertDiv = getEl('div');
            var span = getEl('span');
            span.textContent = 'A package with the name ('+packageName + ') already exists. Please select a new name for this package.'
            addEl(alertDiv, span);
            showYesNoDialog(alertDiv, null, false, true);
    		return;
    	}
  	}
	document.getElementById('packageSubmit').style.display = 'none'
	saveLayoutSetting(quickSaveName, 'package');
}

var existingPackages = null;
function getPackages () {
    return new Promise((resolve, reject) => {
        $.ajax({
            url:'/submit/packages',
            type: 'GET',
            success: function (data) {
                existingPackages = data
            }
        })
    });
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
        var detailContainer = document.getElementById('detailcontainerdiv_' + tabName);
        if (resetTab[tabName] == true || tab.innerHTML == '' || (detailContainer != null && detailContainer.innerHTML == '')) {
            setupTab(tabName);
            resizesTheWindow();
        }
        if (tabName == 'variant' || tabName == 'gene' || tabName == 'info') {
            $(document.getElementById('detailcontainerdiv_' + tabName)).packery();
        }
        changeMenu();
    });
    jobDataLoadingDiv = drawingRetrievingDataDiv(currentTab);
    $.get('/result/service/variantcols', {job_id: jobId, username: username, dbpath: dbPath, confpath: confPath, filter: JSON.stringify(filterJson)}).done(function (jsonResponseData) {
        filterCols = JSON.parse(JSON.stringify(jsonResponseData['columns']['variant']));
        let vcfInfoTypes = {}
        for (let colGroup of jsonResponseData['columns']['sample']) {
            for (let col of colGroup.colModel) {
                vcfInfoTypes[col.col] = col.type;
            }
        }
        for (let colGroup of filterCols) {
            if (colGroup.name === 'vcfinfo') {
                for (let col of colGroup.colModel) {
                    colNameToks = col.col.split('__');
                    baseColName = `base__${colNameToks[1]}`
                    col.type = vcfInfoTypes[baseColName];
                }
            }
        }
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
                if (col.name === 'base') {
                    for (let subCol of col.colModel) {
                        if (subCol.col === 'base__note_gene') {filterCols[0].colModel.push(subCol)}
                      }
                }
                var annotator = col.colModel[0].colgroupkey;
                usedAnnotators['gene'].push(annotator);
                usedAnnotators['info'].push(annotator);
            }
        }
        firstLoadData();
    });
}

function selectTab (tabName) {
    document.querySelector('#tabhead_' + tabName).click();
}

function webresult_run () {
	getPackages();
    getServermode();
    var urlParams = new URLSearchParams(window.location.search);
    username = urlParams.get('username');
    jobId = urlParams.get('job_id');
    dbPath = urlParams.get('dbpath');
    confPath = urlParams.get('confpath');
    if (urlParams.get('separatesample') == 'true') {
        separateSample = true;
    } else {
        separateSample = false;
    }
    $grids = {};
    gridObjs = {};
    if (jobId != null) {
        document.title = 'CRAVAT: ' + jobId;
    } else if (dbPath != null) {
        var toks = dbPath.split('/');
        document.title = 'CRAVAT: ' + toks[toks.length - 1];
        jobId = toks[toks.length - 1];
    }
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
        var target = evt.target;
        var tableHeaderContextmenuId = 'table-header-contextmenu-' + currentTab;
        if (target.closest(tableHeaderContextmenuId) == null) {
            var div = document.getElementById(tableHeaderContextmenuId);
            if (div != null) {
                div.style.display = 'none';
            }
        }
        // closes layout menu.
        if (target.closest('#menu_div') == null) {
            var layoutMenu = document.querySelector('#menu_div .menu1');
            turnOffLayoutMenu();
        }
    });
    checkConnection();
}

function getServermode () {
    fetch('/submit/servermode').then(response=>response.json())
    .then(response=>{
        servermode = response['servermode'];
        if (servermode) {
            fetch('/server/checklogged').then(response=>response.json())
            .then(response=>{
                console.log(response);
                adminMode = response['admin'];
                if (! adminMode) {
                    document.querySelector('#save-pkg-btn').style.display = 'none';
                }
            })
        }
    })
}
