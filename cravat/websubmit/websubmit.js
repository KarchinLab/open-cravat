var servermode = false;
var logged = false;
var username = null;
var prevJobTr = null;
var submittedJobs = [];
var storeModuleDivClicked = false;
var GLOBALS = {
    jobs: [],
    annotators: {},
    reports: {},
    inputExamples: {},
    idToJob: {},
}
var currentTab = 'submit';
var websubmitReportBeingGenerated = {};
var jobRunning = {};

function submit () {
    if (servermode && logged == false) {
        alert('Log in before submitting a job.');
        return;
    }
    let fd = new FormData();
    var textInputElem = $('#input-text');
    var textVal = textInputElem.val();
    let inputFiles = [];
    if (textVal.length > 0) {
        var textBlob = new Blob([textVal], {type:'text/plain'})
        inputFiles.push(new File([textBlob], 'input'));
    } else {
        var fileInputElem = $('#input-file')[0];
        var files = fileInputElem.files;
        if (files.length > 0) {
            for (var i=0; i<files.length; i++) {
                inputFiles.push(files[i]);
            }
        }
    }
    if (inputFiles.length === 0) {
        alert('Choose a input variant files, enter variants, or click an input example button.');
        return;
    }
    document.getElementById('submit-job-button').disabled = true;
    setTimeout(function () {
        document.getElementById('submit-job-button').disabled = false;
    }, 1000);
    for (var i=0; i<inputFiles.length; i++) {
        fd.append('file_'+i,inputFiles[i]);
    }
    var submitOpts = {
        annotators: [],
        reports: []
    }
    var annotChecks = $('#annotator-select-div')
                        .find('.checkbox-group-check');
    for (var i = 0; i<annotChecks.length; i++){
        var cb = annotChecks[i];
        if (cb.checked) {
            submitOpts.annotators.push(cb.value);
        }
    }
    var reportChecks = $('#report-select-div')
                         .find('.checkbox-group-check');
    for (var i = 0; i<reportChecks.length; i++){
        var cb = reportChecks[i];
        if (cb.checked) {
            submitOpts.reports.push(cb.value);
        }
    }
    submitOpts.assembly = $('#assembly-select').val();
    submitOpts.forcedinputformat = $('#submit-input-format-select').val();
    var note = document.getElementById('jobnoteinput').value;
    submitOpts.note = note;
    fd.append('options',JSON.stringify(submitOpts));
    // reads number of input lines
    var reader = new FileReader();
    var lineCount = 0;
    var numFileRead = 0;
    var numInputLineCutoff = parseInt(document.getElementById('settings_num_input_line_warning_cutoff').value);
    reader.onload = function (evt) {
        var file = evt.target.result;
        var allLines = file.split(/\r\n|\n/);
        allLines.forEach((line) => {
            lineCount++;
        });
        numFileRead++;
        if (numFileRead == inputFiles.length) {
            var numAnnots = submitOpts.annotators.length;
            var mapper_vps = 1000;
            var annot_vps = 5000;
            var agg_vps = 8000;
            var runtimeEst = lineCount*(1/mapper_vps + numAnnots/annot_vps + 1/agg_vps);
            if (lineCount > numInputLineCutoff) {
                var sec_num = Math.ceil(runtimeEst);
                var hours   = Math.floor(sec_num / 3600) % 24;
                if (hours > 0) {
                    hours = hours + ' hours ';
                } else if (hours == 1) {
                    hours = hours + ' hour ';
                } else {
                    hours = '';
                }
                var minutes = Math.floor(sec_num / 60) % 60;
                if (minutes > 1) {
                    minutes = minutes + ' minutes ';
                } else if (minutes == 1) {
                    minutes = minutes + ' minute ';
                } else {
                    minutes = '';
                }
                var seconds = sec_num % 60;
                if (seconds <= 1) {
                    seconds = seconds + ' second';
                } else {
                    seconds = seconds + ' seconds';
                }
                var alertDiv = getEl('div');
                var span = getEl('span');
                span.textContent = 'You are submitting ' + lineCount + ' lines of input. Proceed?';
                addEl(alertDiv, span);
                addEl(alertDiv,getEl('br'));
                addEl(alertDiv,getEl('br'));
                var span = getEl('span');
                span.style.fontSize = '12px';
                span.textContent = 'Runtime estimate is ' + hours + minutes + seconds + ' on a system with a solid state drive. Systems with a hard disk will take longer. ';
                addEl(alertDiv, span);
                var span = getEl('span');
                span.style.fontSize = '12px';
                span.textContent = 'Variant number cutoff for this message can be changed at the Settings menu at the top right corner.)';
                addEl(alertDiv, span);
                addEl(alertDiv,getEl('br'));
                showYesNoDialog(alertDiv, commitSubmit, false, false);
            } else {
                commitSubmit();
            }
        }
    };
    for (var i = 0; i < inputFiles.length; i++) {
        reader.readAsText(inputFiles[i]);
    }

    function commitSubmit (proceed) {
        if (proceed == false) {
            return;
        }
        $.ajax({
            url:'submit',
            data: fd,
            type: 'POST',
            processData: false,
            contentType: false,
            success: function (data) {
                if (data['status']['status'] == 'Submitted') {
                    submittedJobs.push(data);
                    addJob(data);
                    sortJobs();
                    buildJobsTable();
                }
                if (data.expected_runtime > 0) {
                }
                jobRunning[data['id']] = true;
            }
        })
        $('#submit-job-button').attr('disabled','disabled');
        setTimeout(function(){
                $('#submit-job-button').removeAttr('disabled');
            },
            1500
        );
    }
};

function sortJobs () {
    for (var i = 0; i < GLOBALS.jobs.length - 1; i++) {
        for (var j = i + 1; j < GLOBALS.jobs.length; j++) {
            var ji1 = GLOBALS.jobs[i];
            var ji2 = GLOBALS.jobs[j];
            var j1 = GLOBALS.idToJob[ji1];
            var j2 = GLOBALS.idToJob[ji2];
            var d1 = new Date(j1.submission_time).getTime();
            var d2 = new Date(j2.submission_time).getTime();
            if (d2 > d1) {
                var tmp = ji1;
                GLOBALS.jobs[i] = GLOBALS.jobs[j];
                GLOBALS.jobs[j] = tmp;
            }
        }
    }
}

function addJob (jsonObj) {
    var trueDate = new Date(jsonObj.submission_time);
    jsonObj.submission_time = trueDate;
    GLOBALS.jobs.push(jsonObj.id);
    GLOBALS.idToJob[jsonObj.id] = jsonObj;
}

function createJobExcelReport (evt) {
    var button = evt.target;
    var jobid = button.getAttribute('jobId');
    if (websubmitReportBeingGenerated[jobid] == undefined) {
        websubmitReportBeingGenerated[jobid] = {};
    }
    websubmitReportBeingGenerated[jobid]['excel'] = true;
    buildJobsTable();
    generateReport(jobid, 'excel', function () {
        websubmitReportBeingGenerated[jobid]['excel'] = false;
        populateJobs().then(function () {
            buildJobsTable();
        });
    });
}

function createJobTextReport (evt) {
    var jobid = evt.target.getAttribute('jobId');
    if (websubmitReportBeingGenerated[jobid] == undefined) {
        websubmitReportBeingGenerated[jobid] = {};
    }
    websubmitReportBeingGenerated[jobid]['text'] = true;
    buildJobsTable();
    generateReport(jobid, 'text', function () {
        websubmitReportBeingGenerated[jobid]['text'] = false;
        populateJobs().then(function () {
            buildJobsTable();
        });
    });
}

function getAnnotatorsForJob (jobid) {
    var jis = GLOBALS.jobs;
    var anns = [];
    for (var j = 0; j < jis.length; j++) {
        var cji = GLOBALS.idToJob[jis[j]];
        if (cji.id == jobid) {
            anns = cji.annotators;
            break;
        }
    }
    return anns;
}

function getAnnotatorVersionForJob (jobid) {
    var jis = GLOBALS.jobs;
    var anns = {};
    for (var j = 0; j < jis.length; j++) {
        var cji = GLOBALS.idToJob[jis[j]];
        if (cji.id == jobid) {
            anns = cji.annotator_version;
            break;
        }
    }
    return anns;
}

function onClickJobTableMainTr (evt) {
    if (evt.target.parentElement.classList.contains('job-table-tr') == false) {
        return;
    }
    var clickedTr = evt.target.parentElement;
    var detailTr = clickedTr.nextSibling;
    if (clickedTr.classList.contains('highlighted-tr')) {
        clickedTr.classList.remove('highlighted-tr');
        detailTr.classList.add('hidden-tr');
    } else {
        clickedTr.classList.add('highlighted-tr');
        detailTr.classList.remove('hidden-tr');
    }
}

function emptyElement (elem) {
    while (elem.firstChild) {
        elem.removeChild(elem.firstChild);
    }
}

function populateJobTr (job) {
    var jobTr = $('tr.job-table-main-tr[jobid=' + job.id + ']')[0];
    emptyElement(jobTr);
    // Input file name
    addEl(jobTr, addEl(getEl('td'), getTn(job.orig_input_fname)));
    // Number of annotators
    var annots = job.annotators;
    if (annots == undefined) {
        annots = '';
    }
    var num = annots.length;
    var td = getEl('td');
    td.style.textAlign = 'center';
    td.textContent = '' + num;
    addEl(jobTr, td);
    // Genome assembly
    var td = getEl('td');
    td.style.textAlign = 'center';
    addEl(td, getTn(job.assembly));
    addEl(jobTr, td);
    // Note
    var td = getEl('td');
    addEl(jobTr, addEl(td, getTn(job.note)));
    // Status
    var statusC = job.status['status'];
    if (statusC == undefined) {
        if (job.status != undefined) {
            statusC = job.status;
        } else {
            return null;
        }
    }
    var viewTd = getEl('td');
    viewTd.style.textAlign  = 'center';
    if (statusC == 'Finished') {
        var a = getEl('a');
        a.setAttribute('href', '/result/index.html?dbpath=' + job.db_path + '&job_id=' + job.id)
        a.setAttribute('target', '_blank');
        var button = getEl('button');
        addEl(button, getTn('Launch'));
        button.disabled = !job.viewable;
        addEl(a, button);
        addEl(viewTd, a);
    } else {
        viewTd.textContent = statusC;
    }
    addEl(jobTr, viewTd);
    var dbTd = getEl('td');
    dbTd.style.textAlign = 'center';
    // Excel
    var excelButton = getEl('button');
    addEl(excelButton, getTn('Excel'));
    excelButton.setAttribute('jobId', job.id);
    if (websubmitReportBeingGenerated[job.id] != undefined && websubmitReportBeingGenerated[job.id]['excel'] == true) {
        excelButton.style.backgroundColor = '#cccccc';
        excelButton.setAttribute('disabled', true);
        excelButton.textContent = 'Generating...';
    } else {
        if (job.reports.includes('excel') == false) {
            excelButton.style.backgroundColor = '#cccccc';
            excelButton.addEventListener('click', createJobExcelReport);
            excelButton.title = 'Click to create.';
        } else {
            excelButton.addEventListener('click', jobExcelDownloadButtonHandler);
            excelButton.title = 'Click to download.';
        }
    }
    addEl(dbTd, excelButton);
    // Text
    var textButton = getEl('button');
    addEl(textButton, getTn('Text'));
    textButton.setAttribute('jobId', job.id);
    if (websubmitReportBeingGenerated[job.id] != undefined && websubmitReportBeingGenerated[job.id]['text'] == true) {
        textButton.style.backgroundColor = '#cccccc';
        textButton.setAttribute('disabled', true);
        textButton.textContent = 'Generating...';
    } else {
        if (job.reports.includes('text') == false) {
            textButton.style.backgroundColor = '#cccccc';
            textButton.addEventListener('click', createJobTextReport);
            textButton.title = 'Click to create.';
        } else {
            textButton.addEventListener('click', jobTextDownloadButtonHandler);
            textButton.title = 'Click to download.';
        }
    }
    addEl(dbTd, textButton);
    // Log
    var logLink = getEl('a');
    logLink.setAttribute('href','jobs/' + job.id + '/log?');
    logLink.setAttribute('target', '_blank');
    logLink.setAttribute('title', 'Click to download.');
    var button = getEl('button');
    addEl(button, getTn('Log'));
    addEl(logLink, button);
    addEl(dbTd, logLink);
    addEl(jobTr, dbTd);
    /*
    // Reports
    var reportTd = $(getEl('td'));
    jobTr.append(reportTd);
    var reportSelector = $(getEl('select'))
        .attr('jobId',job.id)
        .addClass('report-type-selector')
        .change(reportSelectorChangeHandler)
    reportTd.append(reportSelector);
    jobReports = job.reports;
    let firstExistingReport;
    var curSelectedReport = curSelectedReports[job.id];
    for (let i=0; i<GLOBALS.reports.valid.length; i++) {
        let reportType = GLOBALS.reports.valid[i];
        if (firstExistingReport === undefined && jobReports.includes(reportType)) {
            firstExistingReport = reportType;
        }
        let typeOpt = $(getEl('option'))
        .attr('value', reportType)
        .append(reportType[0].toUpperCase()+reportType.slice(1));
        reportSelector.append(typeOpt);
    }
    var shownReportType = curSelectedReport ? curSelectedReport : firstExistingReport;
    reportSelector.val(shownReportType);
    var repDwnBtn = $(getEl('button'))
        .addClass('report-download-button')
        .append('Download')
        .attr('disabled', !job.reports.includes(shownReportType))
        .click(reportDownloadButtonHandler);
    reportTd.append(repDwnBtn);
    repGenBtn = $(getEl('button'))
        .append('Generate')
        .click(reportGenerateButtonHandler)
    reportTd.append(repGenBtn);
    */
    // Delete
    var deleteTd = getEl('td');
    deleteTd.title = 'Click to delete.';
    deleteTd.style.textAlign = 'center';
    var deleteBtn = getEl('button');
    addEl(deleteBtn, getTn('X'));
    addEl(deleteTd, deleteBtn);
    deleteBtn.setAttribute('jobId', job.id);
    deleteBtn.addEventListener('click', jobDeleteButtonHandler);
    addEl(jobTr, deleteTd);
    return true;
}

function populateJobDetailTr (job) {
    var ji = job.id;
    var detailTr = $('tr.job-detail-tr[jobid=' + ji + ']')[0];
    emptyElement(detailTr);
    // Job detail row
    var annots = job.annotators;
    var annotVers = job.annotator_version;
    var annotVerStr = '';
    if (annots == undefined || annots.length == 0) {
        annotVerStr = 'None';
    } else {
        for (var j = 0; j < annots.length; j++) {
            var annot = annots[j];
            var ver = null;
            if (annotVers != undefined) {
                ver = annotVers[annot];
                if (ver == undefined) {
                    ver = null;
                }
            }
            if (ver == null) {
                annotVerStr += annot + ', ';
            } else {
                annotVerStr += annot + '(' + ver + '), ';
            }
        }
        annotVerStr = annotVerStr.replace(/, $/, '');
    }
    var detailTd = getEl('td');
    detailTd.colSpan = '8';
    var detailTable = getEl('table');
    detailTable.style.width = '100%';
    var tbody = getEl('tbody');
    addEl(detailTable, tbody);
    var tr = getEl('tr');
    var td = getEl('td');
    td.style.width = '150px';
    td.textContent = 'Job ID';
    addEl(tr, td);
    var td = getEl('td');
    td.textContent = ji;
    addEl(tr, td);
    addEl(tbody, tr);
    if (job.open_cravat_version != undefined) {
        var tr = getEl('tr');
        var td = getEl('td');
        td.textContent = 'OpenCRAVAT ver';
        addEl(tr, td);
        var td = getEl('td');
        td.textContent = job.open_cravat_version;
        addEl(tr, td);
        addEl(tbody, tr);
    }
    var tr = getEl('tr');
    var td = getEl('td');
    td.textContent = 'Annotators';
    addEl(tr, td);
    var td = getEl('td');
    td.textContent = annotVerStr;
    addEl(tr, td);
    addEl(tbody, tr);
    if (job.num_input_var != undefined) {
        var tr = getEl('tr');
        var td = getEl('td');
        td.textContent = '# input variants';
        addEl(tr, td);
        var td = getEl('td');
        td.textContent = job.num_input_var;
        addEl(tr, td);
        addEl(tbody, tr);
    }
    if (job.submission_time != undefined) {
        var tr = getEl('tr');
        var td = getEl('td');
        td.textContent = 'Submitted';
        addEl(tr, td);
        var td = getEl('td');
        var t = new Date(job.submission_time);
        var month = t.getMonth() + 1;
        if (month < 10) {
            month = '0' + month;
        }
        var d = t.getDate();
        if (d < 10) {
            d = '0' + d;
        }
        var h = t.getHours();
        if (h < 10) {
            h = '0' + h;
        }
        var m = t.getMinutes();
        if (m < 10) {
            m = '0' + m;
        }
        var s = t.getSeconds();
        if (s < 10) {
            s = '0' + s;
        }
        td.textContent = t.getFullYear() + '.' + month + '.' + d + ' ' + h + ':' + m + ':' + s;
        addEl(tr, td);
        addEl(tbody, tr);
    }
    if (job.db_path != undefined) {
        var tr = getEl('tr');
        var td = getEl('td');
        td.textContent = 'Result DB';
        addEl(tr, td);
        var td = getEl('td');
        var button = getEl('button');
        button.textContent = 'DB';
        button.setAttribute('db', job.id);
        button.addEventListener('click', function (evt) {
            window.open('/submit/jobs/' + evt.target.getAttribute('db') + '/db');
        });
        addEl(td, button);
        addEl(tr, td);
        addEl(tbody, tr);
        var tr = getEl('tr');
        var td = getEl('td');
        td.textContent = 'Job Directory';
        addEl(tr, td);
        var td = getEl('td');
        var a = getEl('span');
        var d = job.db_path.substring(0, job.db_path.lastIndexOf('/'));
        /*
        a.href = 'file://///' + d;
        */
        a.textContent = d;
        addEl(td, a);
        addEl(tr, td);
        addEl(tbody, tr);
    }
    addEl(detailTd, detailTable);
    addEl(detailTr, detailTd);
}

function buildJobsTable () {
    var allJobs = GLOBALS.jobs;
    var i = submittedJobs.length - 1;
    while (i >= 0) {
        var submittedJob = submittedJobs[i];
        var alreadyInList = false;
        var submittedJobInList = null;
        for (var j = 0; j < allJobs.length; j++) {
            if (allJobs[j] == submittedJob['id']) {
                alreadyInList = true;
                submittedJobInList = GLOBALS.idToJob[allJobs[j]];
                break;
            }
        }
        if (alreadyInList) {
            if (submittedJobInList['status']['status'] != 'Submitted') {
                var p = submittedJobs.pop();
            }
        } else {
            submittedJob.status = 'Submitted';
            allJobs.unshift(submittedJob.id);
        }
        i--;
    }
    var reportSelectors = $('.report-type-selector');
    var curSelectedReports = {};
    for (let i=0; i<reportSelectors.length; i++) {
        var selector = $(reportSelectors[i]);
        var jobId = selector.attr('jobId');
        var val = selector.val();
        curSelectedReports[jobId] = val;
    }
    var jobsTable = document.querySelector('#jobs-table tbody');
    $(jobsTable).empty();
    for (let i = 0; i < allJobs.length; i++) {
        job = GLOBALS.idToJob[allJobs[i]];
        ji = job.id;
        if (ji == undefined) {
            continue;
        }
        if (job.submission_time == 'Invalid Date') {
            continue;
        }
        var jobTr = getEl('tr');
        jobTr.classList.add('job-table-tr');
        jobTr.classList.add('job-table-main-tr');
        jobTr.setAttribute('jobid', ji);
        jobTr.addEventListener('click', onClickJobTableMainTr);
        addEl(jobsTable, jobTr);
        var ret = populateJobTr(job);
        if (ret == null) {
            jobsTable.removeChild(jobTr);
            continue;
        }
        var detailTr = getEl('tr');
        detailTr.classList.add('job-detail-tr');
        detailTr.classList.add('hidden-tr');
        detailTr.setAttribute('jobid', ji);
        addEl(jobsTable, detailTr);
        populateJobDetailTr(job);
    }
}

function reportSelectorChangeHandler (event) {
    var selector = $(event.target);
    var downloadBtn = selector.siblings('.report-download-button');
    var jobId = selector.attr('jobId');
    var reportType = selector.val();
    var job = GLOBALS.idToJob[jobId];
    /*
    for (let i=0; i<GLOBALS.jobs.length; i++) {
        if (GLOBALS.idToJob[GLOBALS.jobs[i].id] === jobId) {
            job = GLOBALS.jobs[i];
            break;
        }
    }
    */
    downloadBtn.attr('disabled',!job.reports.includes(reportType));
}

function reportDownloadButtonHandler (event) {
    var btn = $(event.target);
    var selector = btn.siblings('.report-type-selector');
    var jobId = selector.attr('jobId');
    var reportType = selector.val();
    downloadReport(jobId, reportType);
}

function downloadReport (jobId, reportType) {
    // url = 'http://'+window.location.host+'/rest/jobs/'+jobId+'/reports/'+reportType;
    url = 'jobs/'+jobId+'/reports/'+reportType;
    downloadFile(url);
}

function generateReport (jobId, reportType, callback) {
    $.ajax({
        url:'jobs/'+jobId+'/reports/'+reportType,
        type: 'POST',
        processData: false,
        contentType: 'application/json',
        success: function (data) {
            callback();
        }
    })
}

function jobExcelDownloadButtonHandler (event) {
    downloadJobExcel($(event.target).attr('jobId'));
}

function jobTextDownloadButtonHandler (event) {
    downloadJobText($(event.target).attr('jobId'));
}

function downloadJobExcel (jobId) {
    url = 'jobs/'+jobId+'/reports/excel';
    downloadFile(url);
}

function downloadJobText (jobId) {
    url = 'jobs/'+jobId+'/reports/text';
    downloadFile(url);
}

function downloadFile (url) {
    $('#download-area').attr('src', url);
}

function getEl (tag) {
    return document.createElement(tag);
}

function jobDeleteButtonHandler (event) {
    event.stopPropagation();
    var jobId = $(event.target).attr('jobId');
    deleteJob(jobId);
}

function deleteJob (jobId) {
    $.ajax({
        url:'jobs/'+jobId,
        type: 'DELETE',
        contentType: 'application/json',
        success: function (data) {
            populateJobs().then(() => {
                buildJobsTable();
            });
        }
    })
    delete jobRunning[jobId];
    let delIdx = null;
    for (var i=0; i<submittedJobs.length; i++) {
        if (submittedJobs[i].id === jobId) {
            delIdx = i;
            break;
        }
    }
    if (delIdx !== null) {
        submittedJobs = submittedJobs.slice(0,delIdx).concat(submittedJobs.slice(delIdx+1));
    }
}

function inputExampleChangeHandler (event) {
    var elem = $(event.target);
    var format = elem.val();
    var assembly = $('#assembly-select').val();
    var formatAssembly = format + '.' + assembly;
    var getExampleText = new Promise((resolve, reject) => {
        var cachedText = GLOBALS.inputExamples[formatAssembly];
        if (cachedText === undefined) {
            var fname = formatAssembly + '.txt';
            $.ajax({
                url:'input-examples/'+fname,
                type: 'GET',
                contentType: 'application/json',
                success: function (data) {
                    GLOBALS.inputExamples[formatAssembly] = data;
                    resolve(data);
                }
            })
        } else {
            resolve(cachedText);
        }
    });
    getExampleText.then((text) => {
        var inputArea = $('#input-text');
        inputArea.val(text);
        inputArea.change();
    })
}

function allNoAnnotatorsHandler (event) {
    var elem = $(event.target);
    let checked;
    if (elem.attr('id') === 'all-annotators-button') {
        checked = true;
    } else {
        checked = false;
    }
    var annotCheckBoxes = $('.annotator-checkbox');
    for (var i = 0; i<annotCheckBoxes.length; i++){
        var cb = annotCheckBoxes[i];
        cb.checked = checked;
    }
}

function inputChangeHandler (event) {
    var target = $(event.target);
    var id = target.attr('id');
    if (id === 'input-file') {
        $('#input-text').val('');
    } else if (id === 'input-text') {
        var elem = $("#input-file");
        elem.wrap('<form>').closest('form').get(0).reset();
        elem.unwrap();
    }
    populateMultInputsMessage();
}

var JOB_IDS = []

function populateJobs () {
    return new Promise((resolve, reject) => {
        $.ajax({
            url:'jobs',
            type: 'GET',
            async: true,
            success: function (allJobs) {
                GLOBALS.jobs = [];
                for (var i=0; i<allJobs.length; i++) {
                    var job = allJobs[i];
                    var status = job.status;
                    if (status == 'Finished' || status == 'Error') {
                        delete jobRunning[job.id];
                    } else {
                        jobRunning[job.id] = true;
                    }
                    addJob(job);
                }
                sortJobs();
                buildJobsTable();
                //resolve();
            },
            fail: function (response) {
                alert('fail at populate jobs');
            }
        })
    });
}

function refreshJobsTable () {
    populateJobs();//.then(buildJobsTable());
}

function populateAnnotators () {
    return new Promise((resolve, reject) => {
        $.ajax({
            url:'annotators',
            type: 'GET',
            success: function (data) {
                GLOBALS.annotators = data
                buildAnnotatorsSelector();
                //resolve();
            }
        })
    });
}

function buildAnnotatorGroupSelector () {
    var annotCheckDiv = document.getElementById('annotator-group-select-div');
    $(annotCheckDiv).empty();
    var div = getEl('div');
    div.className = 'annotator-group-select';
    addEl(annotCheckDiv, div);
    var tagToAnnots = {};
    var checkDatas = [];
    for (var i = 0; i < tagsCollected.length; i++) {
        var tag = tagsCollected[i];
        checkDatas.push({
            name: tag,
            value: tag,
            label: tag,
            checked: false,
            kind: 'tag',
        });
    }
    buildCheckBoxGroup(checkDatas, div);
    addEl(annotCheckDiv, getEl('hr'));
    var checkDatas = [];
    var div = getEl('div');
    div.className = 'annotator-group-select';
    addEl(annotCheckDiv, div);
    var groupNames = Object.keys(installedGroups);
    groupNames.sort();
    for (var i = 0; i < groupNames.length; i++) {
        var name = groupNames[i].replace(/_group$/, '');
        checkDatas.push({
            name: name,
            value: name,
            label: name,
            checked: false,
            kind: 'group',
        });
    }
    buildCheckBoxGroup(checkDatas, div);
    addEl(annotCheckDiv, getEl('hr'));
    var height = annotCheckDiv.offsetHeight;
    var stylesheets = window.document.styleSheets;
    for (var i = 0; i <= stylesheets.length; i++) {
        var stylesheet = stylesheets[i];
        if (stylesheet.href.indexOf('websubmit.css') >= 0) {
            stylesheet.insertRule('#annotator-group-select-div {max-height: ' + height + 'px;}');
            break;
        }
    }
}

function buildAnnotatorsSelector () {
    var annotCheckDiv = document.getElementById('annotator-select-div');
    let annotators = GLOBALS.annotators;
    let annotInfos = Object.values(annotators);
    // Sort by title
    annotInfos.sort((a,b) => {
        var x = a.title.toLowerCase();
        var y = b.title.toLowerCase();
        if (x < y) {return -1;}
        if (x > y) {return 1;}
        return 0;
    });
    let checkDatas = [];
    for (let i=0; i<annotInfos.length; i++) {
        var annotInfo = annotInfos[i];
        checkDatas.push({
            name: annotInfo.name,
            value: annotInfo.name,
            label: annotInfo.title,
            checked: false,
        })
    }
    buildCheckBoxGroup(checkDatas, annotCheckDiv);
}

function getModuleDetailDiv (moduleName) {
    var div = document.getElementById('moduledetaildiv_submit');
    if (div) {
        emptyElement(div);
    } else {
        div = getEl('div');
        div.id = 'moduledetaildiv_submit';
        div.style.position = 'fixed';
        div.style.width = '80%';
        div.style.height = '80%';
        div.style.margin = 'auto';
        div.style.backgroundColor = 'white';
        div.style.left = '0';
        div.style.right = '0';
        div.style.top = '0';
        div.style.bottom = '0';
        div.style.zIndex = '300';
        div.style.border = '6px';
        div.style.padding = '10px';
        div.style.paddingBottom = '23px';
        div.style.border = '1px solid black';
        div.style.boxShadow = '0px 0px 20px';
    }
    currentDetailModule = moduleName;
    div.style.display = 'block';
    var localModule = localModuleInfo[moduleName];
    var table = getEl('table');
    table.style.height = '100px';
    table.style.border = '0px';
    var tr = getEl('tr');
    tr.style.border = '0px';
    var td = getEl('td');
    td.id = 'moduledetaillogotd';
    td.style.width = '120px';
    td.style.border = '0px';
    addEl(tr, td);
    var sdiv = getEl('sdiv');
    sdiv.className = 'moduletile-logodiv';
    var img = addLogo(moduleName, sdiv);
    if (img != null) {
        img.style.height = '86px';
    }
    if (img != null) {
        img.style.maxHeight = '84px';
    } else {
        sdiv.style.position = 'relative';
        sdiv.children[0].style.display = 'none';
    }
    addEl(td, sdiv);
    addEl(tr, td);
    td = getEl('td');
    td.style.border = '0px';
    var span = getEl('div');
    span.style.fontSize = '30px';
    span.textContent = localModule.title;
    addEl(td, span);
    addEl(td, getEl('br'));
    span = getEl('span');
    span.style.fontSize = '12px';
    span.style.color = 'green';
    span.textContent = localModule.type;
    addEl(td, span);
    span = getEl('span');
    span.style.fontSize = '12px';
    span.style.color = 'green';
    span.textContent = ' | ' + localModule.developer.organization;
    addEl(td, span);
    addEl(tr, td);
    td = getEl('td');
    td.style.border = '0px';
    td.style.verticalAlign = 'top';
    td.style.textAlign = 'right';
    var sdiv = getEl('div');
    sdiv.id = 'installstatdiv_' + moduleName;
    sdiv.style.marginTop = '10px';
    sdiv.style.fontSize = '12px';
    if (installInfo[moduleName] != undefined) {
        sdiv.textContent = installInfo[moduleName]['msg'];
    }
    addEl(td, sdiv);
    addEl(tr, td);
    addEl(table, tr);
    addEl(div, table);
    addEl(div, getEl('hr'));
    table = getEl('table');
    table.style.height = 'calc(100% - 100px)';
    table.style.border = '0px';
    tr = getEl('tr');
    tr.style.border = '0px';
    var tdHeight = (window.innerHeight * 0.8 - 150) + 'px';
    td = getEl('td');
    td.style.border = '0px';
    td.style.width = '70%';
    td.style.verticalAlign = 'top';
    td.style.height = tdHeight;
    var mdDiv = getEl('div');
    mdDiv.style.height = '100%';
    mdDiv.style.overflow = 'auto';
    var wiw = window.innerWidth;
    mdDiv.style.maxWidth = (wiw * 0.8 * 0.68) + 'px';
    addEl(td, mdDiv);
    addEl(tr, td);
	$.get('/store/modules/'+moduleName+'/'+'latest'+'/readme').done(function(data){
		mdDiv.innerHTML = data;
        addClassRecursive(mdDiv, 'moduledetaildiv-submit-elem');
	});
    td = getEl('td');
    td.style.width = '30%';
    td.style.border = '0px';
    td.style.verticalAlign = 'top';
    td.style.height = tdHeight;
    var infodiv = getEl('div');
    infodiv.style.height = '100%';
    infodiv.style.overflow = 'auto';
    infodiv.style.maxWidth = (wiw * 0.8 * 0.3) + 'px';
    var d = getEl('div');
    span = getEl('span');
    span.textContent = localModule.description;
    addEl(d, span);
    addEl(infodiv, d);
    addEl(infodiv, getEl('br'));
    d = getEl('div');
    span = getEl('span');
    span.style.fontWeight = 'bold';
    span.textContent = 'Version: ';
    addEl(d, span);
    span = getEl('span');
    span.textContent = localModule['version'];
    addEl(d, span);
    addEl(infodiv, d);
    addEl(infodiv, getEl('br'));
    d = getEl('div');
    span = getEl('span');
    span.style.fontWeight = 'bold';
    span.textContent = 'Maintainer: ';
    addEl(d, span);
    span = getEl('span');
    span.textContent = localModule['developer']['name'];
    addEl(d, span);
    addEl(d, getEl('br'));
    addEl(d, getEl('br'));
    span = getEl('span');
    span.style.fontWeight = 'bold';
    span.textContent = 'e-mail: ';
    addEl(d, span);
    span = getEl('span');
    span.textContent = localModule['developer']['email'];
    addEl(d, span);
    addEl(d, getEl('br'));
    addEl(d, getEl('br'));
    addEl(infodiv, d);
    d = getEl('div');
    span = getEl('span');
    span.style.fontWeight = 'bold';
    span.textContent = 'Citation: ';
    addEl(d, span);
    span = getEl('span');
    span.style.display = 'inline-block';
    span.style.width = 'calc(100% - 120px)';
    span.style.wordWrap = 'break-word';
    span.style.verticalAlign = 'text-top';
    var citation = localModule['developer']['citation'];
    if (citation.startsWith('http')) {
        var a = getEl('a');
        a.href = citation;
        a.target = '_blank';
        a.textContent = citation;
        addEl(span, a);
    } else {
        span.textContent = citation;
    }
    addEl(d, span);
    addEl(infodiv, d);
    addEl(infodiv, getEl('br'));
    d = getEl('div');
    span = getEl('span');
    span.style.fontWeight = 'bold';
    span.textContent = 'Organization: ';
    addEl(d, span);
    span = getEl('span');
    span.textContent = localModule['developer']['organization'];
    addEl(d, span);
    addEl(infodiv, d);
    addEl(infodiv, getEl('br'));
    d = getEl('div');
    span = getEl('span');
    span.style.fontWeight = 'bold';
    span.textContent = 'Website: ';
    addEl(d, span);
    span = getEl('a');
    span.textContent = localModule['developer']['website'];
    span.href = localModule['developer']['website'];
    span.target = '_blank';
    addEl(d, span);
    addEl(infodiv, d);
    addEl(infodiv, getEl('br'));
    d = getEl('div');
    span = getEl('span');
    span.style.fontWeight = 'bold';
    span.textContent = 'Type: ';
    addEl(d, span);
    span = getEl('span');
    span.textContent = localModule['type'];
    addEl(d, span);
    addEl(infodiv, d);
    addEl(infodiv, getEl('br'));
    addEl(td, infodiv);
    addEl(tr, td);
    addEl(table, tr);
    addEl(div, table);
    var el = getEl('div');
    el.style.position = 'absolute';
    el.style.top = '0px';
    el.style.right = '0px';
    el.style.fontSize = '20px';
    el.style.padding = '10px';
    el.style.cursor = 'pointer';
    el.textContent = 'X';
    el.addEventListener('click', function (evt) {
        var pel = evt.target.parentElement;
        pel.parentElement.removeChild(pel);
    });
    addEl(div, el);
    addClassRecursive(div, 'moduledetaildiv-submit-elem');
    return div;
}

function buildCheckBoxGroup (checkDatas, parentDiv) {
    parentDiv = (parentDiv === undefined) ? getEl('div') : parentDiv;
    emptyElement(parentDiv);
    parentDiv.classList.add('checkbox-group');
    // all-none buttons
    var allNoneDiv = getEl('div');
    addEl(parentDiv, allNoneDiv);
    allNoneDiv.className = 'checkbox-group-all-none-div';
    var parentId = parentDiv.id;
    if (parentId == 'annotator-select-div') {
        if (servermode == false) {
            var btn = getEl('button');
            btn.className = 'checkbox-group-all-button';
            btn.textContent = 'All';
            btn.addEventListener('click', function (evt) {
                checkBoxGroupAllNoneHandler (evt);
            });
            addEl(allNoneDiv, btn);
        }
        var btn = getEl('button');
        btn.className = 'checkbox-group-none-button';
        btn.textContent = 'Clear';
        btn.addEventListener('click', function (evt) {
            checkBoxGroupAllNoneHandler (evt);
        });
        addEl(allNoneDiv, btn);
        var div = getEl('div');
        div.id = 'submit-annotator-set-switch';
        var table = getEl('table');
        var tr = getEl('tr');
        var td = getEl('td');
        var span = getEl('span');
        span.textContent = 'Annotator sets';
        addEl(td, span);
        addEl(tr, td);
        addEl(table, tr);
        tr = getEl('tr');
        td = getEl('td');
        var label = getEl('label');
        label.className = 'slider-switch';
        var input = getEl('input');
        input.type = 'checkbox';
        input.checked = true;
        input.addEventListener('change', function (evt) {
            onSubmitClickTagBoxCheck(evt);
        });
        var span = getEl('span');
        span.className = 'slider';
        addEl(label, input);
        addEl(label, span);
        addEl(td, label);
        addEl(tr, td);
        addEl(table, tr);
        addEl(div, table);
        addEl(allNoneDiv, div);
    }
    // flexbox
    var flexbox = getEl('div');
    addEl(parentDiv, flexbox);
    flexbox.classList.add('checkbox-group-flexbox');
    var checkDivs = [];
    // checks
    for (let i=0; i<checkDatas.length; i++) {
        var checkData = checkDatas[i];
        var checkDiv = getEl('div');
        checkDiv.classList.add('checkbox-group-element');
        addEl(flexbox, checkDiv);
        var check = getEl('input');
        check.className = 'checkbox-group-check';
        check.setAttribute('type', 'checkbox');
        check.setAttribute('name', checkData.name);
        check.setAttribute('value', checkData.value);
        check.checked = checkData.checked;
        if (check.kind == 'group') {
            check.setAttribute('members', checkData.members);
        }
        check.setAttribute('kind', checkData.kind);
        if (parentId == 'annotator-select-div') {
            check.id = 'annotator-select-div-input-' + checkData.name;
        }
        if (parentDiv.classList.contains('annotator-group-select')) {
            check.addEventListener('change', function (evt) {
                onChangeAnnotatorGroupCheckbox(evt);
            });
        }
        addEl(checkDiv, check);
        var label = getEl('span');
        //label.style.cursor = 'pointer';
        //label.style.textDecorationLine = 'underline';
        //label.style.textDecorationStyle = 'dotted';
        //label.style.textDecorationColor = '#aaaaaa';
        label.setAttribute('module', checkData.value);
        label.textContent = checkData.label + ' ';
        //label.className = 'moduledetailbutton';
        addEl(checkDiv, label);
        /*label.addEventListener('click', function (evt) {
            var annotchoosediv = document.getElementById('annotchoosediv');
            var moduledetaildiv = document.getElementById('moduledetaildiv_submit');
            if (moduledetaildiv != null) {
                annotchoosediv.removeChild(moduledetaildiv);
            }
            var detaildiv = makeModuleDetailDialog(evt.target.getAttribute('module'));
            addEl(annotchoosediv, detaildiv);
        });*/
        checkDivs.push(checkDiv);
    }
    return parentDiv;
}

function onChangeAnnotatorGroupCheckbox (evt) {
    var checkbox = evt.target;
    var name = checkbox.name;
    var checked = checkbox.checked;
    var kind = checkbox.getAttribute('kind');
    var modules = Object.keys(localModuleInfo);
    if (kind == 'tag') {
        for (var i = 0; i < modules.length; i++) {
            var module = localModuleInfo[modules[i]];
            if (module.tags.indexOf(name) >= 0) {
                var c = document.getElementById('annotator-select-div-input-' + module.name);
                if (c != null) {
                    c.checked = checked;
                }
            }
        }
    } else if (kind == 'group') {
        var members = installedGroups[name + '_group'];
        for (var i = 0; i < members.length; i++) {
            var c = document.getElementById('annotator-select-div-input-' + members[i]);
            if (c != null) {
                c.checked = checked;
            }
        }
    }
}

function checkBoxGroupAllNoneHandler (event) {
    var elem = $(event.target);
    let checked;
    if (elem.hasClass('checkbox-group-all-button')) {
        checked = true;
    } else {
        checked = false;
    }
    var checkElems = elem.closest('.checkbox-group')
                           .find('input.checkbox-group-check');
    for (var i = 0; i<checkElems.length; i++){
        var checkElem = checkElems[i];
        checkElem.checked = checked;
    }
    if (elem[0].parentElement.parentElement.id == 'annotator-select-div') {
        var chk = null;
        var cls = elem[0].className
        if (cls == 'checkbox-group-all-button') {
            chk = true;
        } else if (cls == 'checkbox-group-none-button') {
            chk = false;
        }
        $('#annotator-group-select-div input[type=checkbox]').prop('checked', chk);
    }
}

function populateReports () {
    return new Promise((resolve, reject) => {
        $.ajax({
            url:'reports',
            type: 'GET',
            success: function (data) {
                GLOBALS.reports = data
                buildReportSelector();
                //resolve();
            }
        })
    })
}

function buildReportSelector () {
    var validReports = GLOBALS.reports.valid;
    var checkData = [];
    for (var i=0; i<validReports.length; i++) {
        reportName = validReports[i];
        checkData.push({
            name: reportName,
            value: reportName,
            label: reportName[0].toUpperCase()+reportName.slice(1),
            checked: reportName === GLOBALS.reports.default
        })
    }
    var reportDiv = document.getElementById('report-select-div');
    buildCheckBoxGroup(checkData, reportDiv);
}

function onTabChange () {
    var submitcontentdiv = document.getElementById('submitcontentdiv');
    var jobdiv = document.getElementById('jobdiv');
    var tab = document.getElementById('tabselect').selectedIndex;
    if (tab == 0) {
        submitcontentdiv.style.display = 'block';
        jobdiv.style.display = 'none';
    } else if (tab == 1) {
        submitcontentdiv.style.display = 'none';
        jobdiv.style.display = 'block';
    }
}

function getJobsDir () {
    $.get('/submit/getjobsdir').done(function (response) {
    });
}

function setJobsDir (evt) {
    var d = evt.target.value;
    $.get('/submit/setjobsdir', {'jobsdir': d}).done(function (response) {
        populateJobsTable();
    });
}

function transitionToStore () {
    var submitdiv = document.getElementById('submitdiv');
    var storediv = document.getElementById('storediv');
    var settingsdiv = document.getElementById('settingsdiv');
    submitdiv.style.display = 'none';
    storediv.style.display = 'block';
    settingsdiv.style.display = 'none';
}

function transitionToSubmit () {
    var submitdiv = document.getElementById('submitdiv');
    var storediv = document.getElementById('storediv');
    var settingsdiv = document.getElementById('settingsdiv');
    submitdiv.style.display = 'block';
    storediv.style.display = 'none';
    settingsdiv.style.display = 'none';
}

function transitionToSettings () {
    var settingsdiv = document.getElementById('settingsdiv');
    var submitdiv = document.getElementById('submitdiv');
    var storediv = document.getElementById('storediv');
    submitdiv.style.display = 'none';
    storediv.style.display = 'none';
    settingsdiv.style.display = 'block';
}

function changePage (selectedPageId) {
    var pageselect = document.getElementById('pageselect');
    var pageIdDivs = pageselect.children;
    for (var i = 0; i < pageIdDivs.length; i++) {
        var pageIdDiv = pageIdDivs[i];
        var pageId = pageIdDiv.getAttribute('value');
        var page = document.getElementById(pageId);
        if (page.id == selectedPageId) {
            page.style.display = 'block';
            pageIdDiv.setAttribute('selval', 't');
            if (selectedPageId == 'storediv') {
                currentTab = 'store';
            } else if (selectedPageId == 'submitdiv') {
                currentTab = 'submit';
            }
        } else {
            page.style.display = 'none';
            pageIdDiv.setAttribute('selval', 'f');
        }
    }
}

function openSubmitDiv () {
    var div = document.getElementById('submitcontentdiv');
    div.style.display = 'block';
}

function loadSystemConf () {
    $.get('/submit/getsystemconfinfo').done(function (response) {
        var s = document.getElementById('sysconfpathspan');
        s.value = response['path'];
        var s = document.getElementById('settings_jobs_dir_input');
        s.value = response['content']['jobs_dir'];
        var span = document.getElementById('server_user_span');
        if (! servermode) {
            span.textContent = '/default';
        } else {
            span.textContent = '';
        }
        var s = document.getElementById('settings_modules_dir_input');
        s.value = response['content']['modules_dir'];
        var s = document.getElementById('settings_num_input_line_warning_cutoff');
        var cutoff = response['content']['num_input_line_warning_cutoff'];
        if (cutoff == undefined) {
            cutoff = 250000;
        }
        s.value = cutoff;
    });
}

function onClickSaveSystemConf () {
    document.getElementById('settingsdiv').style.display = 'none';
    updateSystemConf();
}

function updateSystemConf () {
    $.get('/submit/getsystemconfinfo').done(function (response) {
        var s = document.getElementById('sysconfpathspan');
        response['path'] = s.value;
        var s = document.getElementById('settings_jobs_dir_input');
        response['content']['jobs_dir'] = s.value;
        var s = document.getElementById('settings_modules_dir_input');
        response['content']['modules_dir'] = s.value;
        var s = document.getElementById('settings_num_input_line_warning_cutoff');
        response['content']['num_input_line_warning_cutoff'] = s.value;
        $.ajax({
            url:'/submit/updatesystemconf',
            data: {'sysconf': JSON.stringify(response['content'])},
            type: 'GET',
            success: function (response) {
                if (response['success'] == true) {
                    var mdiv = getEl('div');
                    var span = getEl('span');
                    span.textContent = 'System configuration has been updated.';
                    addEl(mdiv, span);
                    addEl(mdiv, getEl('br'));
                    addEl(mdiv, getEl('br'));
                    var justOk = true;
                    showYesNoDialog(mdiv, null, false, justOk);
                } else {
                    var mdiv = getEl('div');
                    var span = getEl('span');
                    span.textContent = 'System configuration was not successful';
                    addEl(mdiv, span);
                    addEl(mdiv, getEl('br'));
                    addEl(mdiv, getEl('br'));
                    var justOk = true;
                    showYesNoDialog(mdiv, null, false, justOk);
                }
                if (response['sysconf']['jobs_dir'] != undefined) {
                    populateJobs();
                    getLocal();
                    populateAnnotators();
                }
            }
        });
    });
}

function resetSystemConf () {
    loadSystemConf();
}

function getServermode () {
    $.ajax({
        url: '/submit/servermode',
        type: 'get',
        success: function (response) {
            servermode = response['servermode'];
            if (servermode == false) {
                setupNoServerMode();
            } else {
                setupServerMode();
            }
        }
    });
}

function setupNoServerMode () {
    document.getElementById('accountdiv').style.display = 'none';
    document.getElementById('headerdiv').style.display = 'block';
    document.getElementById('submitdiv').style.display = 'block';
}

function setupServerMode () {
    document.getElementById('accountdiv').style.display = 'block';
    document.getElementById('settingsdiv').style.display = 'none';
    document.getElementById('threedotsdiv').style.display = 'none';
    //document.getElementById('submitdiv').style.display = 'block';
    //document.getElementById('settingspageselect').style.display = 'none';
    document.getElementById('headerdiv').style.display = 'none';
    document.getElementById('submitdiv').style.display = 'none';
    checkLogged(username);
}

function setupAdminMode () {
    document.getElementById('accountdiv').style.display = 'block';
    document.getElementById('settingsdiv').style.display = 'none';
    document.getElementById('threedotsdiv').style.display = 'block';
    $('#storediv_tabhead[value=storediv]')[0].style.display = 'inline-block';
    //document.getElementById('settingspageselect').style.display = 'inline-block';
}

function showLoggedControl (username) {
    var userDiv = document.getElementById('userdiv');
    userDiv.textContent = username;
    userDiv.style.display = 'inline-block';
    document.getElementById('logoutdiv').style.display = 'inline-block';
    document.getElementById('loginsignupbutton').style.display = 'none';
    document.getElementById('headerdiv').style.display = 'block';
    document.getElementById('submitdiv').style.display = 'block';
}

function showUnloggedControl () {
    var userDiv = document.getElementById('userdiv');
    userDiv.textContent = '';
    userDiv.style.display = 'none';
    document.getElementById('loginsignupbutton').style.display = 'inline-block';
    document.getElementById('logoutdiv').style.display = 'none';
    document.getElementById('threedotsdiv').style.display = 'none';
    $('#storediv_tabhead[value=storediv]')[0].style.display = 'none';
    document.getElementById('submitdiv').style.display = 'block';
    document.getElementById('storediv').style.display = 'none';
    document.getElementById('loginsignupdialog').style.display = 'block';
    document.getElementById('loginsignupbutton').style.display = 'none';
}

function doAfterLogin () {
    showLoggedControl(username);
    hideloginsignupdiv();
    if (username == 'admin') {
        setupAdminMode();
    }
    populateJobs();
}

function msgAccountDiv (msg) {
    document.getElementById('accountmsgdiv').textContent = msg;
    setTimeout(function () {
        document.getElementById('accountmsgdiv').textContent = '';
    }, 3000);
}

function login () {
    var usernameSubmit = document.getElementById('login_username').value;
    var passwordSubmit = document.getElementById('login_password').value;
    $.ajax({
        url: '/submit/login',
        data: {'username':usernameSubmit, 'password':passwordSubmit},
        success: function (response) {
            if (response == 'success') {
                username = usernameSubmit;
                logged = true;
                doAfterLogin();
            } else if (response == 'fail') {
                msgAccountDiv('Login failed');
            }
        }
    });
}

function logout () {
    $.ajax({
        url: '/submit/logout',
        success: function (response) {
            if (response == 'success') {
                username = '';
                logged = false;
                clearJobTable();
                showUnloggedControl();
            }
        }
    });
}

function clearJobTable () {
    $(document.getElementById('jobs-table').tbody).empty();
}

function getPasswordQuestion () {
    var email = document.getElementById('forgotpasswordemail').value;
    $.ajax({
        url: '/submit/passwordquestion',
        data: {'email': email},
        success: function (response) {
            var status = response['status'];
            var msg = response['msg'];
            if (status == 'fail') {
                msgAccountDiv(msg);
            } else {
                document.getElementById('forgotpasswordgetquestiondiv').style.display = 'none';
                document.getElementById('forgotpasswordquestion').textContent = msg;
                document.getElementById('forgotpasswordquestionanswerdiv').style.display = 'inline-block';
            }
        }
    });
}

function showSignupDiv () {
    document.getElementById('logindiv').style.display = 'none';
    document.getElementById('signupdiv').style.display = 'block';
}

function showLoginDiv () {
    document.getElementById('logindiv').style.display = 'block';
    document.getElementById('signupdiv').style.display = 'none';
    document.getElementById('forgotpassworddiv').style.display = 'none';
}

function submitForgotPasswordAnswer () {
    var email = document.getElementById('forgotpasswordemail').value;
    var answer = document.getElementById('forgotpasswordanswer').value;
    $.ajax({
        url: '/submit/passwordanswer',
        data: {'email': email, 'answer': answer},
        success: function (response) {
            var success = response['success'];
            var msg = response['msg'];
            if (success == true) {
                document.getElementById('forgotpassworddiv').style.display = 'none';
                document.getElementById('forgotpasswordemail').textContent = '';
                document.getElementById('forgotpasswordquestion').textContent = '';
                document.getElementById('forgotpasswordanswer').textContent = '';
                alert('Password has been reset to ' + msg);
                showLoginDiv();
            } else {
                msgAccountDiv(msg);
            }
        }
    });
}

function forgotPassword () {
    document.getElementById('logindiv').style.display = 'none';
    document.getElementById('forgotpasswordquestion').textContent = '';
    document.getElementById('forgotpasswordgetquestiondiv').style.display = 'block';
    document.getElementById('forgotpasswordquestionanswerdiv').style.display = 'none';
    document.getElementById('forgotpassworddiv').style.display = 'block';
}

function changePassword () {
    var div = document.getElementById('changepassworddiv');
    var display = div.style.display;
    if (display == 'block') {
        display = 'none';
    } else {
        display = 'block';
    }
    div.style.display = display;
}

function submitNewPassword () {
    var oldpassword = document.getElementById('changepasswordoldpassword').value;
    var newpassword = document.getElementById('changepasswordnewpassword').value;
    var retypenewpassword = document.getElementById('changepasswordretypenewpassword').value;
    if (newpassword != retypenewpassword) {
        msgAccountDiv('New password mismatch');
        return;
    }
    $.ajax({
        url: '/submit/changepassword',
        data: {'oldpassword': oldpassword,
               'newpassword': newpassword},
        success: function (response) {
            if (response == 'success') {
                msgAccountDiv('Password changed successfully.');
                document.getElementById('changepassworddiv').style.display = 'none';
            } else {
                msgAccountDiv(response);
            }
        }
    });
}

function hideloginsignupdiv () {
    document.getElementById('loginsignupdialog').style.display = 'none';
}

function toggleloginsignupdiv () {
    document.getElementById('logindiv').style.display = 'block';
    document.getElementById('signupdiv').style.display = 'none';
    var dialog = document.getElementById('loginsignupdialog');
    var display = dialog.style.display;
    if (display == 'none') {
        display = 'block';
    } else {
        display = 'none';
    }
    dialog.style.display = display;
}

function closeLoginSignupDialog (evt) {
    document.getElementById("loginsignupdialog").style.display="none";
}

function signupSubmit () {
    var username = document.getElementById('signupemail').value.trim();
    var password = document.getElementById('signuppassword').value.trim();
    var retypepassword = document.getElementById('signupretypepassword').value.trim();
    var question = document.getElementById('signupquestion').value.trim();
    var answer = document.getElementById('signupanswer').value.trim();
    if (username == '' || password == '' || retypepassword == '' || question == '' || answer == '') {
        msgAccountDiv('Fill all the blanks.');
        return;
    }
    if (password != retypepassword) {
        msgAccountDiv('Password mismatch');
        return;
    }
    $.ajax({
        url: '/submit/signup',
        data: {'username': username, 'password': password, 'question': question, 'answer': answer},
        success: function (response) {
            if (response == 'already registered') {
                msgAccountDiv('Already registered');
            } else if (response == 'success') {
                populateJobs();
                msgAccountDiv('Account created');
                document.getElementById('loginsignupbutton').style.display = 'none';
                var userDiv = document.getElementById('userdiv');
                userDiv.textContent = username;
                userDiv.style.display = 'inline-block';
                document.getElementById('logoutdiv').style.display = 'inline-block';
                toggleloginsignupdiv();
                document.getElementById('loginsignupbutton').style.display = 'none';
                document.getElementById('signupdiv').style.display = 'none';
                document.getElementById('headerdiv').style.display = 'block';
            } else if (response == 'fail') {
                msgAccountDiv('Signup failed');
            }
        }
    });
}

function checkLogged (username) {
    $.ajax({
        url: '/submit/checklogged',
        headers: {'Cache-Control': 'no-cache'},
        data: {'username': username},
        success: function (response) {
            logged = response['logged'];
            if (logged == true) {
                username = response['email'];
                logged = true;
                doAfterLogin();
            } else {
                showUnloggedControl();
            }
        }
    });
}

function populatePackageVersions () {
    $.get('/submit/packageversions').done(function(data){
        var curverspans = document.getElementsByClassName('curverspan');
        for (var i = 0; i < curverspans.length; i++) {
            var curverspan = curverspans[i];
            var a = getEl('a');
            a.href = "https://github.com/KarchinLab/open-cravat/wiki/Release-Notes";
            a.target = '_blank';
            a.textContent = data.current;
            addEl(curverspan, a);
            if (data.update) {
                var a = getEl('a');
                a.href = 'https://github.com/KarchinLab/open-cravat/wiki/Update-Instructions';
                a.target = '_blank';
                a.textContent = '(' + data.latest + ')';
                addEl(curverspan, a);
            }
        }
	});
}

function onClickInputTextArea () {
    let input = document.getElementById('input-text');
    input.rows = 20;
}

function onBlurInputTextArea () {
    let input = document.getElementById('input-text');
    input.rows = 1;
}

function onClickThreeDots (evt) {
    var div = document.getElementById('settingsdiv');
    var display = div.style.display;
    if (display == 'block') {
        display = 'none';
    } else {
        display = 'block';
    }
    div.style.display = display;
    evt.stopPropagation();
}

function openTerminal () {
    $.ajax({
        url: '/submit/openterminal',
    });
}

function resizePage () {
    var div = document.getElementById('submit-form');
    var h = window.innerHeight - 195;
    div.style.height = h + 'px';
    var div = document.getElementById('jobdiv');
    var h = window.innerHeight - 125;
    div.style.height = h + 'px';
}

function fileInputChange(event) {
    var fileInputElem = event.target;
    var files = fileInputElem.files;
    if (files.length > 1) {
        $('#mult-inputs-message').css('display','block');
        var $fileListDiv = $('#mult-inputs-list');
        $fileListDiv.empty();
        for (var i=0; i<files.length; i++) {
            var file = files[i];
            var $p = $(getEl('p'))
                .text(file.name);
            $fileListDiv.append($p);
        }
    } else {
        $('#mult-inputs-message').css('display','none');
    }
}

function populateMultInputsMessage() {
    var fileInputElem = document.getElementById('input-file');
    var files = fileInputElem.files;
    if (files.length > 1) {
        $('#mult-inputs-message').css('display','block');
        var $fileListDiv = $('#mult-inputs-list');
        $fileListDiv.empty();
        for (var i=0; i<files.length; i++) {
            var file = files[i];
            var $p = $(getEl('p'))
                .text(file.name);
            $fileListDiv.append($p);
        }
    } else {
        $('#mult-inputs-message').css('display','none');
    }
}

function addListeners () {
    $('#submit-job-button').click(submit);
    $('#input-text').change(inputChangeHandler);
    $('#input-file').change(inputChangeHandler);
    $('#all-annotators-button').click(allNoAnnotatorsHandler);
    $('#no-annotators-button').click(allNoAnnotatorsHandler);
    $('.input-example-button').click(inputExampleChangeHandler)
    $('#refresh-jobs-table-btn').click(refreshJobsTable);
    $('#threedotsdiv').click(onClickThreeDots);
    $('.jobsdirinput').change(setJobsDir);
    document.addEventListener('click', function (evt) {
        if (evt.target.classList.contains('moduledetaildiv-submit-elem') == false && evt.target.closest('.moduledetailbutton') == null ) {
            var div = document.getElementById('moduledetaildiv_submit');
            if (div != null) {
                div.style.display = 'none';
            }
        }
        if (evt.target.classList.contains('moduledetaildiv-store-elem') == false) {
            var div = document.getElementById('moduledetaildiv_store');
            if (div != null) {
                div.style.display = 'none';
            }
            storeModuleDivClicked = false;
        } else {
            storeModuleDivClicked = true;
        }
        if (evt.target.id != 'settingsdots' && evt.target.id != 'settingsdiv' && evt.target.classList.contains('settingsdiv-elem') == false) {
            var div = document.getElementById('settingsdiv');
            if (div != null) {
                div.style.display = 'none';
            }
        }
    });
    window.addEventListener('resize', function (evt) {
        var moduledetaildiv = document.getElementById('moduledetaildiv_submit');
        if (moduledetaildiv != null) {
            var tdHeight = (window.innerHeight * 0.8 - 150) + 'px';
            var tds = document.getElementById('moduledetaildiv_submit').getElementsByTagName('table')[1].getElementsByTagName('td');
            tds[0].style.height = tdHeight;
            tds[1].style.height = tdHeight;
        }
        var moduledetaildiv = document.getElementById('moduledetaildiv_store');
        if (moduledetaildiv != null) {
            var tdHeight = (window.innerHeight * 0.8 - 150) + 'px';
            var tds = document.getElementById('moduledetaildiv_store').getElementsByTagName('table')[1].getElementsByTagName('td');
            tds[0].style.height = tdHeight;
            tds[1].style.height = tdHeight;
        }
    });
    document.addEventListener('keyup', function (evt) {
        if (storeModuleDivClicked) {
            var k = evt.key;
            var moduleDiv = document.getElementById('moduledetaildiv_store');
            var moduleListName = moduleDiv.getAttribute('modulelistname');
            var moduleListPos = moduleDiv.getAttribute('modulelistpos');
            var moduleList = moduleLists[moduleListName];
            if (k == 'ArrowRight') {
                var moduleName = null;
                while (true) {
                    moduleListPos++;
                    if (moduleListPos >= moduleList.length) {
                        moduleListPos = 0;
                    }
                    moduleName = moduleList[moduleListPos];
                }
                makeModuleDetailDialog(moduleName, moduleListName, moduleListPos);
                evt.stopPropagation();
            } else if (k == 'ArrowLeft') {
                var moduleName = null;
                while (true) {
                    moduleListPos--;
                    if (moduleListPos < 0) {
                        moduleListPos = moduleList.length - 1;
                    }
                    moduleName = moduleList[moduleListPos];
                }
                makeModuleDetailDialog(moduleName, moduleListName, moduleListPos);
                evt.stopPropagation();
            }
        }
    });
}

function setLastAssembly () {
    $.ajax({
        url: '/submit/lastassembly',
        ajax: true,
        success: function (response) {
            document.getElementById('assembly-select').value = response;
        },
    });
}

function getJobById (jobId) {
    return GLOBALS.idToJob[jobId];
    /*
    for (var i = 0; i < GLOBALS.jobs.length; i++) {
        var job = GLOBALS.jobs[i];
        if (job.id == jobId) {
            return job;
        }
    }
    */
    return null;
}

function updateRunningJobTrs (job) {
    populateJobTr(job);
    populateJobDetailTr(job);
}

function onSubmitClickTagBoxCheck (evt) {
    var div = document.getElementById('annotator-group-select-div');
    if (evt.target.checked) {
        div.className = 'on';
    } else {
        div.className = 'off';
    }
}

function onSubmitTagCheckboxChange () {
}

function websubmit_run () {
    getServermode();
    //var storediv = document.getElementById('storediv');
    //storediv.style.display = 'none';
    connectWebSocket();
    checkConnection();
    setLastAssembly();
    getBaseModuleNames();
    getRemote();
    addListeners();
    if (servermode == false) {
        populateJobs();
    }
    populateAnnotators();
    /*
    if (servermode == false) {
        populateReports();
    }
    */
    //getJobsDir();
    resizePage();
    window.onresize = function (evt) {
        resizePage();
    }
    loadSystemConf();
    populatePackageVersions();
    populateMultInputsMessage();
    setInterval(function () {
        var runningJobIds = Object.keys(jobRunning);
        if (runningJobIds.length == 0) {
            return;
        }
        $.ajax({
            url: '/submit/getjobs',
            data: {'ids': JSON.stringify(runningJobIds)},
            ajax: true,
            success: function (response) {
                for (var i=0; i < response.length; i++) {
                    var job = response[i];
                    GLOBALS.idToJob[job.id] = job;
                    /*
                    for (var j = 0; j < GLOBALS.jobs; j++) {
                        if (job.id == GLOBALS.jobs[j].id) {
                            GLOBALS.jobs[j] = job;
                            break;
                        }
                    }
                    */
                    updateRunningJobTrs(job);
                    if (job.status == 'Finished') {
                        delete jobRunning[job.id];
                    }
                }
            },
        });
    }, 1000);
};

