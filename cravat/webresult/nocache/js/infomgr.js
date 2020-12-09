function InfoMgr () {
	this.datas = {};
	this.columnnoss = {};
	this.columnss = {};
	this.colModels = {};
	this.columngroupss = {};
	this.columngroupkeys = {};
	this.colgroupkeytotitle = {};
	this.colgrouptitletokey = {};
	this.stats = {};
	this.statuss = {};
	this.jobinfo = {};
	this.widgetReq = {};
    this.colgroupdefaulthiddenexist = {};
    this.modulesInfo = {};
}

InfoMgr.prototype.getStatus = function (jobId) {
	var self = this;
	self.jobId = jobId;
}

InfoMgr.prototype.count = function (dbPath, tabName, callback) {
	const data = {
		username: username, 
		job_id: jobId, 
		tab: tabName, 
		dbpath: dbPath,
		filter: JSON.stringify(filterJson),
	};
	$.post('/result/service/count', data).done(function (jsonResponseData) {
		var msg = jsonResponseData['n'] + ' variants meet the criteria';
		callback(msg, jsonResponseData);
	});	
}

InfoMgr.prototype.load = function (jobId, tabName, callback, callbackArgs, fJson, fetchtype) {
	var self = this;
	if (fetchtype == 'job') {
		if (jobDataLoadingDiv == null) {
			drawingRetrievingDataDiv(tabName);
		}
		if (filterJson === []){ //TODO find and fix the cause of this
			filterJson = {};
		}
		$.ajax({
			url: '/result/service/result', 
			type: 'post',
			async: true,
			data: {'username': username, job_id: jobId, tab: tabName, dbpath: dbPath, confpath: confPath, filter: JSON.stringify(filterJson), separatesample: separateSample},
			success: function (jsonResponseData) {
				self.store(self, tabName, jsonResponseData, callback, callbackArgs);
				writeLogDiv(tabName + ' data loaded');
                addTextToInfonoticediv(jsonResponseData['warning_msgs']);
                if (tabName == 'variant') {
					var loaded = jsonResponseData.data.length;
					var total = parseInt(infomgr.jobinfo['Number of unique input variants']);
					var filterTab = document.getElementById('tabhead_filter');
					var filterTitle = 'FILTER';
					if (loaded != total) {
						filterTitle += ` ${loaded.toLocaleString()}/${total.toLocaleString()}`;
						filterTab.classList.add('active');
					} else {
						filterTab.classList.remove('active');
					}
					filterTab.innerText = filterTitle;
					var vCountLoad = document.getElementById('filter-count-display');
					vCountLoad.innerText = `${loaded.toLocaleString()}/${total.toLocaleString()} variants`
					if (Object.keys(filterJson) !== 0) {
						filterMgr.updateAll(filterJson);
					}
                }
			}
	    });
	} else if (fetchtype == 'single') {
		$.get('/submit/annotate', {mutation: onemut, dbcolumn: true}).done(function (jsonResponseData) {
	    	self.datas[tabName] = [jsonResponseData];
	    	self.jobinfo = {}
	    	self.jobinfo['inputcoordinate'] = 'genomic';
	    	if (callback != null) {
	    		callback(callbackArgs);
	    	}
		});
	} else if (fetchtype == 'info') {
		$.get('/result/service/status', {'username': username, 'job_id': jobId, dbpath: dbPath}).done(function (jsonResponseData) {
			self.jobinfo = jsonResponseData;
			if (callback != null) {
				callback(callbackArgs);
			}
	    });
	}
}

InfoMgr.prototype.store = function (self, tabName, jsonResponseData, callback, callbackArgs) {
	resetTab[tabName] = true;
	if (Object.keys(jsonResponseData).length == 0) {
		if (callback != null) {
			callback(callbackArgs);
		} else {
			return;
		}
	}
	self.datas[tabName] = jsonResponseData['data'];
	self.colModels[tabName] = jsonResponseData['columns'];
	self.stats[tabName] = jsonResponseData['stat'];
	self.statuss[tabName] = jsonResponseData['status'];
    self.modulesInfo[tabName] = jsonResponseData['modules_info'];
	if (tabName == 'gene') {
		self.geneRows = {};
		for (var i = 0; i < self.datas[tabName].length; i++) {
			var row = self.datas[tabName][i];
			self.geneRows[row[0]] = row;
		}
	}
	var colModel = self.colModels[tabName];
	var columnnos = {};
	var columngroups = {};
	var columns = [];
    self.colgroupdefaulthiddenexist[tabName] = {};
	for (var i = 0; i < colModel.length; i++) {
		var colsInGroup = colModel[i]['colModel'];
        var defaultHiddenInGroup = false;
		for (var j = 0; j < colsInGroup.length; j++) {
			var column = colsInGroup[j];
            if (column.default_hidden == true) {
                defaultHiddenInGroup = true;
            }
			columns.push(column);
			column['sortType'] =
				function (row1, row2, dataIndx) {
					var val1 = row1[dataIndx];
					var val2 = row2[dataIndx];
					var decision = -1;
					if (val1 == null) {
						if (val2 == null) {
							decision = 0;
						} else {
							if (ascendingSort[dataIndx]) {
								decision = 1;
							} else {
								decision = -1;
							}
						};
					} else {
						if (val2 == null) {
							if (ascendingSort[dataIndx]) {
								decision = -1;
							} else {
								decision = 1;
							}
						} else if (val1 < val2) {
							decision = -1;
						} else if (val1 > val2) {
							decision = 1;
						} else if (val1 == val2) {
							decision = 0;
						};
					};
					return decision;
				};
			column['render'] = function (ui) {
				var val = ui.rowData[ui.dataIndx];
				var content;
				if (ui.column.type==="float") {
					if (val==null){
						val = '';
						content = '';
					} else if (val === 0) {
						content = '0';
					} else if (Math.abs(val)>1e4 || Math.abs(val)<1e-4) {
						content = val.toExponential(3);
					} else {
						let rnd = Math.round((val+Number.EPSILON)*1e4)/1e4;
						content = rnd.toString();
					}
				} else {
					if (val == null) {
						val = '';
					}
					content = '' + val;
				}
                content = content.replace(/>/g, '&gt;');
				var title = content;
				if (ui.column.link_format !== null) {
					var linkFormat = ui.column.link_format;
					var linkRe = /\$\{(.*)\}/;
					var linkMatch = linkFormat.match(linkRe);
					var valSegment = '';
					var linkUrl = '';
					var linkText = '';
					if (linkMatch !== null) {
						var reString = linkMatch[1];
						var valRe = new RegExp(reString);
						var valMatch = val.match(valRe)
						if (valMatch !== null && valMatch[0] !== '') {
							if (valMatch.length===1) {
								valSegment = valMatch[0];
							} else {
								valSegment = '';
								for (var i=1; i<valMatch.length; i++) {
									valSegment += valMatch[i];
								}
							}
							var linkUrl = linkFormat.replace(linkRe, valSegment);
							var linkText = val;
						}
					}
					content = `<a href="${linkUrl}" target="_blank">${linkText}</a>`;
					title = linkUrl;
				} else if (content.startsWith('http')) {
					content = `<a href="${content}" target="_blank">View</a>`;
				}
				return `<span title="${title}">${content}</span>`;
			};
            var filter = column['filter'];
            if (filter != undefined && filter['type'] == 'select') {
                var colType = column['type'];
                var colCtg = column['ctg'];
                if (colType == 'string' && colCtg == 'single') {
                    column['filter']['condition'] = function (val, select) {
                        if (select == '' || select == null) {
                            return true;
                        }
                        var selects = JSON.parse(select);
                        if (Array.isArray(selects) && selects.length == 0) {
                            return true;
                        }
                        if (selects.indexOf(val) >= 0) {
                            return true;
                        } else {
                            return false;
                        }
                    };
                } else if (colType == 'string' && colCtg == 'multi') {
                    column['filter']['condition'] = function (val, selects) {
                        if (selects == null) {
                            return true;
                        }
                        var selects = JSON.parse(selects);
                        if (Array.isArray(selects) && selects.length == 0) {
                            return true;
                        }
                        for (var i = 0; i < selects.length; i++) {
                            var select = selects[i];
                            if (val.indexOf(select) >= 0) {
                                return true;
                            }
                        }
                        return false;
                    };
                }
                var selectallText = '';
                if (column['categories'].length > 3) {
                    column['filter']['init'] = function () {
                        $(this).pqSelect({
                            checkbox: true, 
                            displayText: '&#x25BC;',
                            singlePlaceholder: '&#x25BD;',
                            multiplePlaceholder: '&#x25BD;',
                            radio: true, 
                            maxDisplay: 0,
                            search: false,
                            selectallText: 'Select all',
                            width: '90%',});
                        this[0].nextSibling.classList.add('ui-state-hover');
                    };
                } else {
                    column['filter']['init'] = function () {
                        $(this).pqSelect({
                            checkbox: true, 
                            displayText: '&#x25BC;',
                            singlePlaceholder: '&#x25BD;',
                            multiplePlaceholder: '&#x25BD;',
                            radio: true, 
                            maxDisplay: 0,
                            search: false,
                            selectallText: '',
                            width: '90%',});
                        this[0].nextSibling.classList.add('ui-state-hover');
                    };
                }
            }
			var columnKey = column['col'];
			var columnNo = column['dataIndx'];
			columnnos[columnKey] = columnNo;
			var columnGroup = column['colgroup'];
			var columnGroupKey = column['colgroupkey'];
			if (columngroups[columnGroupKey] == undefined) {
				columngroups[columnGroupKey] = [];
			}
			columngroups[columnGroupKey].push(columnKey);
			self.columngroupkeys[columnGroupKey] = columnGroupKey;
			self.colgroupkeytotitle[columnGroupKey] = columnGroup;
			self.colgrouptitletokey[columnGroup] = columnGroupKey;
		}
        colModel[i].default_hidden_exist = defaultHiddenInGroup;
        self.colgroupdefaulthiddenexist[tabName][colModel[i].name] = defaultHiddenInGroup;
	}
	self.columnss[tabName] = columns;
	self.columnnoss[tabName] = columnnos;
	self.columngroupss[tabName] = columngroups;
	
	if (callback != null) {
		callback(callbackArgs);
	}
	
    /*
	if (jobDataLoadingDiv != null) {
		jobDataLoadingDiv.parentElement.removeChild(jobDataLoadingDiv);
		jobDataLoadingDiv = null;
	}
    */
}

InfoMgr.prototype.getData = function (tabName) {
	return this.datas[tabName];
}

InfoMgr.prototype.getColumns = function (tabName) {
	return this.columnss[tabName];
}

InfoMgr.prototype.getColModel = function (tabName) {
	return this.colModels[tabName];
}

InfoMgr.prototype.getColumnGroups = function (tabName) {
	return this.columngroupss[tabName];
}

InfoMgr.prototype.getColumnByName = function (tabName, columnName) {
	return this.columnss[tabName][this.columnnoss[tabName][columnName]];
}

InfoMgr.prototype.getColumnNos = function (tabName) {
	if (Object.keys(this.columnnoss).length == 0) {
		return undefined;
	} else {
		return this.columnnoss[tabName];
	}
}

InfoMgr.prototype.getColumnNo = function (tabName, col) {
	if (Object.keys(this.columnnoss).length == 0) {
		return undefined;
	} else {
		return this.columnnoss[tabName][col];
	}
}

InfoMgr.prototype.getStat = function (tabName) {
	return this.stats[tabName];
}

InfoMgr.prototype.getJobInfo = function (tabName) {
	return this.jobinfo;
}

InfoMgr.prototype.getRowValue = function (tabName, row, col) {
	var val = null;
	if (Object.keys(this.columnnoss).length > 0) {
		val = row[this.columnnoss[tabName][col]];
	} else {
		val = row[col];
	}
	return val;
}

InfoMgr.prototype.getGeneRowValue = function (hugo) {
	var val = null;
	if (Object.keys(this.columnnoss).length > 0) {
		val = row[this.columnnoss[tabName][col]];
	} else {
		val = row[col];
	}
	return val;
}

InfoMgr.prototype.getVariantColumnGroupByName = function (groupName) {
    var colGroups = this.colModels.variant;
    for (var i = 0; i < colGroups.length; i++) {
        var cg = colGroups[i];
        if (cg.title == groupName) {
            return cg;
        }
    }
    return null;
}

