'use strict';
import {
    getTn, addEl, getEl, changePage, PubSub, OC, titleCase, emptyElement, checkVisible
} from './core.js'
import {
    connectWebSocket, checkConnection, getBaseModuleNames, toggleChatBox
} from '../../store/nocache/webstore.js';
import {
    populateAnnotators, makeModuleDetailDialog
} from './moduleinfo.js';
import { loadSystemConf } from './header.js'

OC.servermode = false;
OC.logged = false;
OC.username = null;
OC.prevJobTr = null;
OC.submittedJobs = [];
OC.storeModuleDivClicked = false;
OC.GLOBALS = {
    jobs: [],
    annotators: {},
    reports: {},
    inputExamples: {},
    idToJob: {},
    usersettings: {},
}
OC.currentTab = 'submit';
OC.websubmitReportBeingGenerated = {};
OC.jobRunning = {};
OC.tagsCollectedForSubmit = [];
OC.jobsPerPageInList = 15;
OC.jobsListCurStart = 0;
OC.jobsListCurEnd = OC.jobsPerPageInList;
OC.systemReadyObj = {};
OC.formData = null;
OC.adminMode = false;
OC.inputFileList = [];
OC.JOB_IDS = []
OC.jobListUpdateIntervalFn = null;
OC.reportRunning = {};
OC.systemConf;

function submit () {
    if (OC.servermode && OC.logged == false) {
        alert('Log in before submitting a job.');
        return;
    }
    if (OC.systemConf.save_metrics === 'empty') {
    	informMetrics()
    }
    OC.formData = new FormData();
    var textInputElem = $('#input-text');
    var textVal = textInputElem.val();
    let inputFiles = [];
    let inputServerFiles = []
    if (OC.inputFileList.length > 0 && textVal.length > 0) {
        var alertDiv = getEl('div');
        var span = getEl('span');
        span.textContent = 'Use only one of "Add input files" and the input box'
        addEl(alertDiv, span);
        OC.mediator.publish('showyesnodialog', alertDiv, null, false, true);
        return
    }
    if (textVal.length > 0) {
        if (textVal.startsWith("#serverfile")) {
            let toks = textVal.split("\n")
            for (var i = 1; i < toks.length; i++) {
                let tok = toks[i]
                if (tok == "") {
                    continue
                }
                inputServerFiles.push(tok.trim())
            }
        } else {
            var textBlob = new Blob([textVal], {type:'text/plain'})
            inputFiles.push(new File([textBlob], 'input'));
        }
    } else {
        inputFiles = OC.inputFileList;
    }
    if (inputFiles.length === 0 && inputServerFiles.length == 0) {
        alert('Choose a input variant files, enter variants/server input file paths, or click an input example button.');
        return;
    }
    for (var i=0; i<inputFiles.length; i++) {
        OC.formData.append('file_'+i,inputFiles[i]);
    }
    var submitOpts = {
        annotators: [],
        reports: [],
    	packages: ''
    }
    var allAnnotsDiv = document.getElementById('annotchoosediv');
    if (allAnnotsDiv.style.display !== 'none') {
	    var annotChecks = $('#annotator-select-div').find('input[type=checkbox][kind=module]');
	    for (var i = 0; i<annotChecks.length; i++){
	        var cb = annotChecks[i];
	        if (cb.checked) {
	            submitOpts.annotators.push(cb.value);
	        }
	    }
    }
    var allPackagesDiv = document.getElementById('packagechoosediv');
    if (allPackagesDiv.style.display !== 'none') {
    	var selPackage = document.getElementById('package-select-dropdown').value;
    	if (selPackage !== 'none') {
    		submitOpts.packages = selPackage;
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
    var assmSelect = $('#assembly-select');
    var assembly = assmSelect.val();
    if (assembly !== null) {
        submitOpts.assembly = assembly;
    } else {
        OC.mediator.publish('showyesnodialog', 'Please select a genome version', ()=>{
            $('#assembly-select-div').css('border', '2px solid red');
            setTimeout(()=>{$('#assembly-select-div').css('border', 'none');},2000);
        }, false, true);
        return;
    }
    submitOpts.forcedinputformat = $('#submit-input-format-select').val();
    var note = document.getElementById('jobnoteinput').value;
    submitOpts.note = note;
    submitOpts.inputServerFiles = inputServerFiles
    document.querySelector('#submit-job-button').disabled = true;
    OC.formData.append('options',JSON.stringify(submitOpts));
    // AddtlAnalysis
    for (let addtlName of addtlAnalysis.names) {
        let addtlData = addtlAnalysis.fetchers[addtlName]();
        if (addtlData != undefined) {
            OC.formData.append(addtlName, addtlAnalysis.fetchers[addtlName]());
        }
    }
    var guiInputSizeLimit = parseInt(document.getElementById('settings_gui_input_size_limit').value);
    var sumInputSize = 0;
    for (var i = 0; i < inputFiles.length; i++) {
        sumInputSize += inputFiles[i].size;
    }
    sumInputSize = sumInputSize / 1024 / 1024;
    if (sumInputSize > guiInputSizeLimit) {
        var alertDiv = getEl('div');
        var span = getEl('span');
        span.textContent = 'Input files are limited to ' + guiInputSizeLimit.toFixed(1) + ' MB.';
        addEl(alertDiv, span);
        addEl(alertDiv,getEl('br'));
        if (!OC.servermode) {
            addEl(alertDiv,getEl('br'));
            var span = getEl('span');
            span.textContent = 'The limit can be changed at the settings menu.';
            addEl(alertDiv, span);
            addEl(alertDiv,getEl('br'));
        }
        OC.mediator.publish('showyesnodialog', alertDiv, enableSubmitButton, false, true);
    } else {
        commitSubmit();
    }
    
    function enableSubmitButton () {
        document.querySelector('#submit-job-button').disabled = false;
    }

    function commitSubmit (flag) {
        if (flag == false) {
            document.querySelector('#submit-job-button').disabled = false;
            return;
        }
        showSpinner();
        var req = new XMLHttpRequest();
        req.open('POST', '/submit/submit');
        //req.setRequestHeader('Content-Type', 'multipart/form-data; boundary=blob');
        req.upload.onprogress = function (evt) {
            var uploadPerc = evt.loaded / evt.total * 100;
            document.querySelector('#spinner-div-progress-bar').style.width = uploadPerc + '%';            
            document.querySelector('#spinner-div-progress-num').textContent = uploadPerc.toFixed(0) + '%';            
        };
        req.onload = function (evt) {
            document.querySelector('#submit-job-button').disabled = false;
            hideSpinner();
            const status = evt.currentTarget.status;
            if (status === 200) {
                var response = JSON.parse(evt.currentTarget.response);
                if (response['status']['status'] == 'Submitted') {
                    OC.submittedJobs.push(response);
                    addJob(response, true);
                    //sortJobs();
                    buildJobsTable();
                }
                if (response.expected_runtime > 0) {
                }
                OC.jobRunning[response['id']] = true;
            } else if (status>=400 && status<600) {
                var response = JSON.parse(evt.currentTarget.response);
                var alertDiv = getEl('div');
                var h3 = getEl('h3');
                h3.textContent = 'Upload Failure';
                addEl(alertDiv, h3);
                var span = getEl('span');
                span.textContent = 'This is often caused by improper input files. Check that your input is in a form OpenCRAVAT accepts.'
                addEl(alertDiv, span);
                addEl(alertDiv,getEl('br'));
                addEl(alertDiv,getEl('br'));
                var span = getEl('span');
                span.innerHTML = 'If you think this was caused by an error, <a href="mailto:support@opencravat.org">let us know</a>'
                addEl(alertDiv,span);
                addEl(alertDiv,getEl('br'));
                addEl(alertDiv,getEl('br'));
                var span = getEl('span');
                span.innerText = 'Details: '+response.msg;
                addEl(alertDiv,span);
                OC.mediator.publish('showyesnodialog', alertDiv, null, false, true);

            }
        };
        req.onerror = function (evt) {
            document.querySelector('#submit-job-button').disabled = false;
            hideSpinner();
        }
        req.onabort = function (evt) {
            document.querySelector('#submit-job-button').disabled = false;
            hideSpinner();
        }
        req.send(OC.formData);
    }
};

function showSpinner () {
    document.querySelector('#spinner-div').classList.add('show');
    document.querySelector('#spinner-div').classList.remove('hide');
}

function hideSpinner () {
    document.querySelector('#spinner-div').classList.remove('show');
    document.querySelector('#spinner-div').classList.add('hide');
}

function showUpdateRemoteSpinner () {
    document.querySelector('#update-remote-spinner-div').classList.remove('hide');
    document.querySelector('#update-remote-spinner-div').classList.add('show');
}

function hideUpdateRemoteSpinner () {
    document.querySelector('#update-remote-spinner-div').classList.remove('show');
    document.querySelector('#update-remote-spinner-div').classList.add('hide'); 
}

function sortJobs () {
    for (var i = 0; i < OC.GLOBALS.jobs.length - 1; i++) {
        for (var j = i + 1; j < OC.GLOBALS.jobs.length; j++) {
            var ji1 = OC.GLOBALS.jobs[i];
            var ji2 = OC.GLOBALS.jobs[j];
            var j1 = OC.GLOBALS.idToJob[ji1];
            var j2 = OC.GLOBALS.idToJob[ji2];
            var d1 = new Date(j1.submission_time).getTime();
            var d2 = new Date(j2.submission_time).getTime();
            if (d2 > d1) {
                var tmp = ji1;
                OC.GLOBALS.jobs[i] = OC.GLOBALS.jobs[j];
                OC.GLOBALS.jobs[j] = tmp;
            }
        }
    }
}

function addJob (job, prepend) {
    var trueDate = new Date(job.submission_time);
    job.submission_time = trueDate;
    if (OC.GLOBALS.jobs.indexOf(job.id) == -1) {
        if (prepend == true) {
            OC.GLOBALS.jobs.unshift(job.id);
        } else {
            OC.GLOBALS.jobs.push(job.id);
        }
    }
    OC.GLOBALS.idToJob[job.id] = job;
    var status = job.status;
    if (status != 'Finished' && status != 'Error' && status != 'Aborted') {
        OC.jobRunning[job.id] = true;
    } else if (OC.jobRunning[job.id] != undefined) {
        delete OC.jobRunning[job.id];
    }
    if (job.reports_being_generated.length > 0) {
        OC.websubmitReportBeingGenerated[job.id] = {};
        if (OC.reportRunning[job.id] == undefined) {
            OC.reportRunning[job.id] = {};
        }
        for (var i = 0; i < job.reports_being_generated.length; i++) {
            var reportType = job.reports_being_generated[i];
            OC.websubmitReportBeingGenerated[job.id][reportType] = true;
            OC.reportRunning[job.id][reportType] = true;
        }
    }
}

function createJobReport (evt) {
    var div = document.querySelector('#report_generation_div');
    var jobId = div.getAttribute('jobid');
    closeReportGenerationDiv();
    var select = document.querySelector('#report_generation_div_select');
    var reportType = select.value;
    if (OC.websubmitReportBeingGenerated[jobId] == undefined) {
        OC.websubmitReportBeingGenerated[jobId] = {};
    }
    OC.websubmitReportBeingGenerated[jobId][reportType] = true;
    buildJobsTable();
    generateReport(jobId, reportType, function () {
        if (OC.websubmitReportBeingGenerated[jobId] == undefined) {
            delete OC.websubmitReportBeingGenerated[jobId];
        } else {
            //websubmitReportBeingGenerated[jobId][reportType] = false;
            delete OC.websubmitReportBeingGenerated[jobId][reportType];
            populateJobs().then(function () {
                buildJobsTable();
            });
        }
    });
}

function generateReport (jobId, reportType, callback) {
    $.ajax({
        url:'/submit/jobs/'+jobId+'/reports/'+reportType,
        type: 'POST',
        //processData: false,
        contentType: 'application/json',
        success: function (data) {
            if (data == 'fail') {
                var mdiv = getEl('div');
                var span = getEl('span');
                span.textContent = reportType + ' report generation failed for ' + jobId;
                addEl(mdiv, span);
                addEl(mdiv, getEl('br'));
                addEl(mdiv, getEl('br'));
                var span = getEl('span');
                span.textContent = 'Check your system\'s wcravat.log for details.';
                addEl(mdiv, span);
                OC.mediator.publish('showyesnodialog', mdiv, null, false, true);
            }
            callback();
        }
    });
    if (OC.reportRunning[jobId] == undefined) {
        OC.reportRunning[jobId] = {};
    }
    OC.reportRunning[jobId][reportType] = true;
}

function getAnnotatorsForJob (jobid) {
    var jis = OC.GLOBALS.jobs;
    var anns = [];
    for (var j = 0; j < jis.length; j++) {
        var cji = OC.GLOBALS.idToJob[jis[j]];
        if (cji.id == jobid) {
            anns = cji.annotators;
            break;
        }
    }
    return anns;
}

function getAnnotatorVersionForJob (jobid) {
    var jis = OC.GLOBALS.jobs;
    var anns = {};
    for (var j = 0; j < jis.length; j++) {
        var cji = OC.GLOBALS.idToJob[jis[j]];
        if (cji.id == jobid) {
            anns = cji.annotator_version;
            break;
        }
    }
    return anns;
}

function informMetrics () {
    var alertDiv = getEl('div');
    var span = getEl('span');
    var a = getEl('a');
    a.href = 'https://open-cravat.readthedocs.io/en/latest/Metrics.html';
    a.target = '_blank';
    a.textContent = 'visit OC Metric documentation';
    span.textContent = 'OpenCRAVAT gathers metrics to report usage to funders and improve the tool. No private data is collected. For more details, visit our documentation at '
    addEl(alertDiv, span);
    addEl(alertDiv, a);
    OC.mediator.publish('showyesnodialog', alertDiv, null, false, true);
    var s = document.getElementById('settings_save_metrics');
    s.checked = true;
    updateSystemConf(true);
    OC.systemConf.save_metrics = true;
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

function populateJobTr (job) {
    var jobTr = $('tr.job-table-main-tr[jobid=' + job.id + ']')[0];
    emptyElement(jobTr);
    // Username 
    if (OC.adminMode == true) {
        var td = getEl('td');
        addEl(td, getTn(job.username));
        addEl(jobTr, td);
    }
    // Job ID
    addEl(jobTr, addEl(getEl('td'), getTn(job.id)));
    // Input file name
    if (Array.isArray(job.orig_input_fname)) {
        input_fname = job.orig_input_fname.join(', ');
    } else {
        var input_fname = job.orig_input_fname;
    }
    var input_fname_display = input_fname;
    var input_fname_display_limit = 30;
    if (input_fname.length > input_fname_display_limit) {
        input_fname_display = input_fname.substring(0, input_fname_display_limit) + '...';
    }
    addEl(jobTr, addEl(getEl('td'), getTn(input_fname_display)));
    // Number of unique variants
    var td = getEl('td');
    td.style.textAlign = 'center';
    var num = '';
    if (job.num_unique_var != undefined) {
        num = '' + job.num_unique_var;
    }
    td.textContent = num;
    addEl(jobTr, td);
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
        if (job.result_available) {
            var a = getEl('a');
            a.setAttribute('href', '/result/index.html?job_id=' + job.id)
            a.setAttribute('target', '_blank');
            var button = getEl('button');
            addEl(button, getTn('Open Result Viewer'));
            button.classList.add('butn');
            button.classList.add('launch-button');
            button.disabled = !job.viewable;
            addEl(a, button);
            addEl(viewTd, a);
        } else {
            var button = getEl('button');
            button.textContent = 'Update to View';
            button.classList.add('butn');
            button.classList.add('launch-button');
            button.disabled = !job.viewable;
            button.setAttribute('job_id', job.id);
            button.addEventListener('click', function (evt) {
                this.textContent = 'Updating DB...';
                var jobId = this.getAttribute('job_id');
                $.ajax({
                    url: '/submit/updateresultdb',
                    type: 'GET',
                    data: {job_id: jobId},
                    success: function (response) {
                        showJobListPage();
                    }
                });
            });
            addEl(viewTd, button);
        }
    } else {
        var span = getEl('span')
        span.textContent = statusC
        addEl(viewTd, span)
        if (statusC == 'Aborted' || statusC == 'Error') {
            var btn = getEl('button')
            btn.classList.add('butn')
            btn.textContent = 'Resubmit'
            btn.addEventListener('click', function(evt) {
                $.get('/submit/resubmit', {'job_id': job.id, 'job_dir': job.job_dir}).done(function (response) {
                    setTimeout(function() {populateJobs()}, 3000)
                })
            })
            addEl(viewTd, btn)
        }
    }
    addEl(jobTr, viewTd);
    var dbTd = getEl('td');
    dbTd.style.textAlign = 'center';
    // Reports
    for (var i = 0; i < OC.GLOBALS.reports.valid.length; i++) {
        var reportType = OC.GLOBALS.reports.valid[i];
        if ((OC.websubmitReportBeingGenerated[job.id] != undefined && OC.websubmitReportBeingGenerated[job.id][reportType] == true) || job.reports_being_generated.includes(reportType)) {
            var btn = getEl('button');
            btn.classList.add('butn');
            btn.setAttribute('jobid', job.id);
            btn.setAttribute('report-type', reportType);
            addEl(btn, getTn(reportType.toUpperCase()));
            btn.setAttribute('disabled', true);
            btn.classList.add('inactive-download-button');
            var spinner = getEl('img');
            spinner.classList.add('btn_overlay');
            spinner.src = '/result/images/arrow-spinner.gif';
            addEl(btn, spinner);
            if (job.status == 'Finished') {
                addEl(dbTd, btn);
            }
        } else {
            if (job.reports.includes(reportType) == false) {
            } else {
                var btn = getEl('button');
                btn.classList.add('butn');
                btn.setAttribute('jobid', job.id);
                btn.setAttribute('report-type', reportType);
                addEl(btn, getTn(reportType.toUpperCase()));
                btn.classList.add('active-download-button');
                btn.addEventListener('click', function (evt) {jobReportDownloadButtonHandler(evt);});
                btn.title = 'View log';
                if (job.status == 'Finished') {
                    addEl(dbTd, btn);
                }
            }
        }
    }
    // DB
    var dbLink = getEl('a');
    addEl(dbTd, dbLink);
    var dbButton = getEl('button');
    addEl(dbLink, dbButton);
    dbButton.classList.add('butn');
    dbLink.setAttribute('title', 'Download output database.');
    addEl(dbButton, getTn('DB'));
    if (job.status === 'Finished') {
        dbLink.setAttribute('href','/submit/jobs/' + job.id + '/db');
        dbLink.setAttribute('target', '_blank');
        dbButton.classList.add('active-download-button');
    } else {
        dbButton.classList.add('inactive-download-button');
    }
    addEl(jobTr, dbTd);
    // Log
    var logLink = getEl('a');
    logLink.setAttribute('href','/submit/jobs/' + job.id + '/log');
    logLink.setAttribute('target', '_blank');
    logLink.setAttribute('title', 'Click to download.');
    var logButton = getEl('button');
    logButton.classList.add('butn');
    logButton.classList.add('active-download-button');
    addEl(logButton, getTn('Log'));
    addEl(logLink, logButton);
    addEl(dbTd, logLink);
    addEl(jobTr, dbTd);
    // Err
    var errLink = getEl('a');
    addEl(dbTd, errLink);
    var errButton = getEl('button');
    addEl(errLink, errButton);
    errButton.classList.add('butn');
    if (job.num_error_input > 0) {
        errButton.classList.add('active-download-button');
        errLink.setAttribute('href','/submit/jobs/' + job.id + '/err');
        errLink.setAttribute('target', '_blank');
        errLink.setAttribute('title', 'View per-variant errors.');
    } else {
        errButton.classList.add('inactive-download-button');
        errLink.setAttribute('title', 'No errors.');
    }
    addEl(errButton, getTn('Errors'));
    addEl(jobTr, dbTd);
    // + button
    var btn = getEl('button');
    btn.classList.add('butn');
    btn.setAttribute('jobid', job.id);
    addEl(btn, getTn('+'));
    btn.classList.add('inactive-download-button');
    btn.addEventListener('click', function (evt) {
        var repSelDiv = document.querySelector('#report_generation_div');
        if (repSelDiv.classList.contains('show')) {
            repSelDiv.classList.remove('show');
            return;
        }
        var jobId = evt.target.getAttribute('jobid');
        var job = OC.GLOBALS.idToJob[jobId];
        var select = document.querySelector('#report_generation_div_select');
        while (select.options.length > 0) {
            select.remove(0);
        }
        for (var i = 0; i < OC.GLOBALS.reports.valid.length; i++) {
            var reportType = OC.GLOBALS.reports.valid[i];
            if (OC.websubmitReportBeingGenerated[job.id] != undefined && OC.websubmitReportBeingGenerated[job.id][reportType] == true) {
            } else {
                var option = new Option(reportType, reportType);
                select.add(option);
            }
        }
        var div2 = document.querySelector('#report_generation_div');
        div2.setAttribute('jobid', jobId);
        div2.style.top = (evt.clientY + 2) + 'px';
        div2.style.right = (window.innerWidth - evt.clientX) + 'px';
        div2.classList.add('show');
    });
    btn.title = 'Click to open report generator.';
    addEl(dbTd, btn);
    // Delete
    var deleteTd = getEl('td');
    deleteTd.title = 'Click to delete.';
    deleteTd.style.textAlign = 'center';
    var deleteBtn = getEl('button');
    deleteBtn.classList.add('butn');
    deleteBtn.classList.add('inactive-download-button');
    /*deleteBtn.classList.add('active-download-button');*/
    addEl(deleteBtn, getTn('X'));
    addEl(deleteTd, deleteBtn);
    deleteBtn.setAttribute('jobId', job.id);
    deleteBtn.addEventListener('click', jobDeleteButtonHandler);
    addEl(jobTr, deleteTd);
    return true;
}

function closeReportGenerationDiv (evt) {
    var div = document.querySelector('#report_generation_div');
    div.classList.remove('show');
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
    td.style.width = '160px';
    td.textContent = 'Annotators';
    addEl(tr, td);
    var td = getEl('td');
    td.textContent = annotVerStr;
    addEl(tr, td);
    addEl(tbody, tr);
    if (job.num_unique_var != undefined) {
        var tr = getEl('tr');
        var td = getEl('td');
        td.textContent = '# unique input variants';
        addEl(tr, td);
        var td = getEl('td');
        td.textContent = job.num_unique_var;
        addEl(tr, td);
        addEl(tbody, tr);
    }
    if (job.submission_time != undefined) {
        var tr = getEl('tr');
        var td = getEl('td');
        td.textContent = 'Submitted';
        addEl(tr, td);
        var td = getEl('td');
        if (job.submission_time == 'Invalid Date') {
            td.textContent = '';
        } else {
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
        }
        addEl(tr, td);
        addEl(tbody, tr);
    }
    if (job.job_dir != undefined) {
        var tr = getEl('tr');
        var td = getEl('td');
        td.textContent = 'Job Directory';
        addEl(tr, td);
        var td = getEl('td');
        var a = getEl('span');
        a.textContent = job.job_dir;
        addEl(td, a);
        addEl(tr, td);
        addEl(tbody, tr);
    }
    // input files
    var input_fname = job.orig_input_fname;
    if (Array.isArray(job.orig_input_fname)) {
        input_fname = job.orig_input_fname.join(', ');
    }
    var tr = getEl('tr');
    var td = getEl('td');
    td.textContent = 'Input file(s)';
    addEl(tr, td);
    var td = getEl('td');
    var sdiv = getEl('div');
    sdiv.style.maxHeight = '80px';
    sdiv.style.overflow = 'auto';
    sdiv.textContent = input_fname;
    addEl(td, sdiv);
    addEl(tr, td);
    addEl(tbody, tr);
    addEl(detailTd, detailTable);
    addEl(detailTr, detailTd);
}

function buildJobsTable () {
    var allJobs = OC.GLOBALS.jobs;
    var i = OC.submittedJobs.length - 1;
    while (i >= 0) {
        var submittedJob = OC.submittedJobs[i];
        var alreadyInList = false;
        var submittedJobInList = null;
        for (var j = 0; j < allJobs.length; j++) {
            if (allJobs[j] == submittedJob['id']) {
                alreadyInList = true;
                submittedJobInList = OC.GLOBALS.idToJob[allJobs[j]];
                break;
            }
        }
        if (alreadyInList) {
            if (submittedJobInList['status']['status'] != 'Submitted') {
                var p = OC.submittedJobs.pop();
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
    var headerTr = document.querySelector('#jobs-table thead tr');
    if (OC.adminMode == true) {
        var firstTd = headerTr.firstChild;
        if (firstTd.textContent != 'User') {
            var td = getEl('th');
            td.textContent = 'User';
            headerTr.prepend(td);
        }
    }
    var jobsTable = document.querySelector('#jobs-table tbody');
    $(jobsTable).empty();
    fillJobTable(allJobs, OC.jobsListCurStart, OC.jobsListCurEnd, jobsTable);
}

function fillJobTable (allJobs, start, end, jobsTable) {
    for (let i = start; i < Math.min(end, allJobs.length); i++) {
        const job = OC.GLOBALS.idToJob[allJobs[i]];
        if (job == undefined) {
            continue;
        }
        const ji = job.id;
        if (ji == undefined) {
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

function onClickJobsListPrevPage () {
    OC.jobsListCurEnd -= OC.jobsPerPageInList;
    if (OC.jobsListCurEnd < OC.jobsPerPageInList) {
        OC.jobsListCurEnd = OC.jobsPerPageInList;
    }
    OC.jobsListCurStart = OC.jobsListCurEnd - OC.jobsPerPageInList;
    OC.jobsListCurStart = Math.min(Math.max(0, OC.jobsListCurStart), OC.GLOBALS.jobs.length);
    OC.jobsListCurEnd = Math.max(0, Math.min(OC.jobsListCurEnd, OC.GLOBALS.jobs.length));
    showJobListPage();
}

function onClickJobsListNextPage () {
    OC.jobsListCurStart += OC.jobsPerPageInList;
    if (OC.jobsListCurStart >= OC.GLOBALS.jobs.length) {
        OC.jobsListCurStart = OC.GLOBALS.jobs.length - (OC.GLOBALS.jobs.length % OC.jobsPerPageInList);
    }
    OC.jobsListCurEnd = OC.jobsListCurStart + OC.jobsPerPageInList;
    OC.jobsListCurStart = Math.min(Math.max(0, OC.jobsListCurStart), OC.GLOBALS.jobs.length);
    OC.jobsListCurEnd = Math.max(0, Math.min(OC.jobsListCurEnd, OC.GLOBALS.jobs.length));
    showJobListPage();
}

function reportSelectorChangeHandler (event) {
    var selector = $(event.target);
    var downloadBtn = selector.siblings('.report-download-button');
    var jobId = selector.attr('jobId');
    var reportType = selector.val();
    var job = OC.GLOBALS.idToJob[jobId];
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

function jobReportDownloadButtonHandler (evt) {
    var btn = evt.target;
    var jobId = btn.getAttribute('jobid');
    var reportType = btn.getAttribute('report-type');
    downloadReport(jobId, reportType);
}

function downloadReport (jobId, reportType) {
    const url = '/submit/jobs/'+jobId+'/reports/'+reportType;
    downloadFile(url);
}

function downloadFile (url) {
    $('#download-area').attr('src', url);
}

function jobDeleteButtonHandler (event) {
    event.stopPropagation();
    var jobId = $(event.target).attr('jobId');
    document.querySelectorAll('#jobs-table tr.job-table-tr[jobid="' + jobId + '"] td').forEach(function (el) {
        el.classList.add('strikenout');
    });
    deleteJob(jobId);
}

function deleteJob (jobId) {
    $.ajax({
        url:'/submit/jobs/'+jobId,
        type: 'DELETE',
        contentType: 'application/json',
        success: function (data) {
            populateJobs().then(() => {
                showJobListPage();
            });
        }
    })
    delete OC.jobRunning[jobId];
    let delIdx = null;
    for (var i=0; i<OC.submittedJobs.length; i++) {
        if (OC.submittedJobs[i].id === jobId) {
            delIdx = i;
            break;
        }
    }
    if (delIdx !== null) {
        OC.submittedJobs = OC.submittedJobs.slice(0,delIdx).concat(OC.submittedJobs.slice(delIdx+1));
    }
}

function inputExampleChangeHandler (event) {
    var elem = $(event.target);
    var format = elem.val();
    var assembly = 'hg38';
    var formatAssembly = format + '.' + assembly;
    var getExampleText = new Promise((resolve, reject) => {
        var cachedText = OC.GLOBALS.inputExamples[formatAssembly];
        if (cachedText === undefined) {
            var fname = formatAssembly + '.txt';
            $.ajax({
                url:'/submit/input-examples/'+fname,
                type: 'GET',
                contentType: 'application/json',
                success: function (data) {
                    clearInputFiles();
                    document.querySelector('#input-file').value = '';
                    OC.GLOBALS.inputExamples[formatAssembly] = data;
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
        $('#assembly-select').val(assembly);
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

function showJobListPage () {
    var jis = OC.GLOBALS.jobs.slice(OC.jobsListCurStart, OC.jobsListCurEnd);
    document.querySelector("#jobdivspinnerdiv").classList.remove("hide")
    $.ajax({
        url: '/submit/getjobs',
        data: {'ids': JSON.stringify(jis)},
        async: true,
        success: function (response) {
            document.querySelector("#jobdivspinnerdiv").classList.add("hide")
            for (var i=0; i < response.length; i++) {
                var job = response[i];
                addJob(job);
            }
            buildJobsTable();
            if (OC.jobListUpdateIntervalFn == null) {
                OC.jobListUpdateIntervalFn = setInterval(function () {
                    var runningJobIds = Object.keys(OC.jobRunning);
                    var runningReportIds = Object.keys(OC.reportRunning);
                    var combinedIds = runningJobIds.concat(runningReportIds);
                    if (combinedIds.length == 0) {
                        return;
                    }
                    $.ajax({
                        url: '/submit/getjobs',
                        data: {'ids': JSON.stringify(combinedIds)},
                        ajax: true,
                        success: function (response) {
                            try {
                                for (var i=0; i < response.length; i++) {
                                    var job = response[i];
                                    OC.GLOBALS.idToJob[job.id] = job;
                                    if (job.status == 'Finished' || job.status == 'Aborted' || job.status == 'Error') {
                                        delete OC.jobRunning[job.id];
                                    }
                                    if (OC.reportRunning[job.id] != undefined) {
                                        var reportTypes = Object.keys(OC.reportRunning[job.id]);
                                        for (var j = 0; j < reportTypes.length; j++) {
                                            var reportType = reportTypes[j];
                                            if (job.reports.includes(reportType)) {
                                                delete OC.reportRunning[job.id][reportType];
                                                delete OC.websubmitReportBeingGenerated[job.id][reportType];
                                                if (Object.keys(OC.reportRunning[job.id]).length == 0) {
                                                    delete OC.reportRunning[job.id];
                                                    delete OC.websubmitReportBeingGenerated[job.id];
                                                }
                                            }
                                        }
                                    }
                                    updateRunningJobTrs(job);
                                }
                            } catch (e) {
                                console.error(e);
                            }
                        },
                        error: function (e) {
                            console.error(e);
                        }
                    });
                }, 5000);
            }
        }
    });
}

function populateJobs () {
    return new Promise((resolve, reject) => {
        $.ajax({
            url:'/submit/jobs',
            type: 'GET',
            async: true,
            success: function (response) {
                OC.GLOBALS.jobs = response;
                OC.jobsListCurStart = 0;
                OC.jobsListCurEnd = OC.jobsListCurStart + OC.jobsPerPageInList;
                showJobListPage();
            },
            fail: function (response) {
                alert('fail at populate jobs');
            }
        })
    });
}

function refreshJobsTable () {
    populateJobs();
}

function populatePackages () {
    document.querySelector("#package-select-div").classList.remove("show")
    return new Promise((resolve, reject) => {
        $.ajax({
            url:'/submit/packages',
            type: 'GET',
            success: function (data) {
                document.querySelector("#package-select-div").classList.add("show")
                OC.GLOBALS.packages = data
                setTimeout(function () {
                    buildPackagesSelector();
                    resolve();
                }, 100);
            }
        })
    });
}

function buildAnnotatorGroupSelector () {
    OC.tagsCollectedForSubmit = [];
    const tagMembership = {};
    for (var module in OC.localModuleInfo) {
        if (OC.localModuleInfo[module].type != 'annotator') {
            continue;
        }
        var tags = OC.localModuleInfo[module].tags;
        for (var i = 0; i < tags.length; i++) {
            var tag = tags[i];
            if (OC.tagsCollectedForSubmit.indexOf(tag) == -1) {
                OC.tagsCollectedForSubmit.push(tag);
                tagMembership[tag] = 1;
            } else {
                tagMembership[tag]++;
            }
        }
    }
    OC.tagsCollectedForSubmit.sort((a,b)=>{return tagMembership[b]-tagMembership[a]});
    var annotCheckDiv = document.getElementById('annotator-group-select-div');
    $(annotCheckDiv).empty();

    var annotCheckTitleDiv = getEl('div');
    addEl(annotCheckDiv, annotCheckTitleDiv);
    annotCheckTitleDiv.style.display = 'flex';
    annotCheckTitleDiv.style['margin-bottom'] = '3px';
    var div = getEl('div');
    addEl(annotCheckTitleDiv, div);
    div.innerText = 'Categories';
    div.style['font-size'] = '1.2em';
    div.style['font-weight'] = 'bold';
    var div = getEl('div');
    addEl(annotCheckTitleDiv, div);
    div.innerText = 'Show';
    div.style['margin-left'] = 'auto';
    div.style['margin-right'] = '0.5ch';
    div.style['font-weight'] = 'bold';
    div.style['padding'] = '1px';
    var wrapper = getEl('div');
    wrapper.id = 'annotator-group-select-tag-div';
    wrapper.className = 'annotator-group-select';
    addEl(annotCheckDiv, wrapper);
    var checkDatas = [];
    checkDatas.push({
        name: 'selected',
        value: 'selected',
        label: 'selected',
        checked: false,
        kind: 'collect',
    });
    for (var i = 0; i < OC.tagsCollectedForSubmit.length; i++) {
        var tag = OC.tagsCollectedForSubmit[i];
        checkDatas.push({
            name: tag,
            value: tag,
            label: tag,
            checked: false,
            kind: 'tag',
        });
    }
    var select = getEl('select');
    addEl(wrapper, select);
    select.id = 'annotator-group-select-select';
    select.multiple = true;
    for (var i = 0; i < OC.tagsCollectedForSubmit.length; i++) {
        var tagName = OC.tagsCollectedForSubmit[i];
        var option = new Option(tagName, tagName);
        addEl(select, option);
    }
    select.addEventListener('change',function (evt) {
        var tags = $(this).val();
        onChangeAnnotatorGroupCheckbox(tags);
    });
    select.style.display = 'none';
    var tagWrapper = getEl('div');
    tagWrapper.classList.add('checkbox-group-flexbox');
    addEl(wrapper, tagWrapper);
    for (let tag of OC.tagsCollectedForSubmit) {
        let tagDiv = getEl('div');
        tagDiv.classList.add('submit-annot-tag');
        addEl(tagWrapper, tagDiv);
        let tagCb = getEl('input');
        addEl(tagDiv, tagCb);
        tagCb.classList.add('submit-annot-tag-cb');
        tagCb.type = 'checkbox';
        tagCb.value = tag;
        tagCb.style.display = 'none';
        tagCb.addEventListener('change', event=>{
            for (let option of select.options) {
                if (option.value === tag) {
                    option.selected = event.target.checked;
                }
            }
            select.dispatchEvent(new Event('change'));
            tagDiv.classList.toggle('selected');
        });
        let cbId = `annot-control-${tag}`;
        tagCb.id = cbId;
        let tagSpan = getEl('label');
        addEl(tagDiv, tagSpan);
        // tagSpan.setAttribute('for', cbId);
        tagSpan.innerText = titleCase(tag);
        tagSpan.style.cursor = 'pointer';
        tagSpan.style['user-select'] = 'none';
        //TODO do without jquery
        tagDiv.addEventListener('click', ()=>{$(tagCb).click()});
    }
    // Way down here to use local variables in listener
    var allCatsBtn = getEl('button');
    addEl(annotCheckTitleDiv, allCatsBtn);
    allCatsBtn.classList.add('butn');
    allCatsBtn.innerText = 'All';
    allCatsBtn.addEventListener('click', ()=>{
        document.querySelectorAll('.submit-annot-tag')
            .forEach(tagDiv=>{tagDiv.classList.add('selected')});
        document.querySelectorAll('.submit-annot-tag-cb')
            .forEach(cb=>{cb.checked=true});
        for (let option of select.options) {
            option.selected = true;
        }
        select.dispatchEvent(new Event('change'));
    });
    var clearCatsBtn = getEl('button');
    addEl(annotCheckTitleDiv, clearCatsBtn);
    clearCatsBtn.classList.add('butn');
    clearCatsBtn.innerText = 'None';
    clearCatsBtn.addEventListener('click', ()=>{
        document.querySelectorAll('.submit-annot-tag')
        .forEach(tagDiv=>{tagDiv.classList.remove('selected')});
        document.querySelectorAll('.submit-annot-tag-cb')
        .forEach(cb=>{cb.checked=false});
        for (let option of select.options) {
            option.selected = false;
        }
        select.dispatchEvent(new Event('change'));
    });
    var showSelBtn = getEl('button');
    addEl(annotCheckTitleDiv, showSelBtn);
    showSelBtn.classList.add('butn');
    showSelBtn.innerText = 'Selected';
    
    showSelBtn.addEventListener('click',()=>{
        document.querySelectorAll('.submit-annot-tag')
            .forEach(tagDiv=>{tagDiv.classList.remove('selected')});
        document.querySelectorAll('.submit-annot-tag-cb')
            .forEach(cb=>{cb.checked=false});
        for (let option of select.options) {
            option.selected = false;
        }
        onChangeAnnotatorGroupCheckbox(['selected']);
    });
}

function buildPackagesSelector () {
    var packages = OC.GLOBALS.packages;
    var packageDiv = document.getElementById('package-select-div');
    if (packages && Object.keys(packages).length===0) {
        packageDiv.style.display = 'none';
        document.querySelector('#show-package').style.display = 'none';
        document.querySelector('#divbanner-annot').style.display = 'none'
    } else {
        packageDiv.style.display = '';
        document.querySelector('#show-package').style.display = '';
        document.querySelector('#divbanner-annot').style.display = ''
    }
    $(packageDiv).empty();
    var space = getEl('br');
    
    var packageDropdown = getEl('select');
    packageDropdown.id = 'package-select-dropdown';
	var elnone= getEl('option');
	elnone.textContent= 'None Selected';
	elnone.value= 'none';
	addEl(packageDropdown, elnone);

    for (const [key, value] of Object.entries(packages)) {
    	var packageKey = `${key}`
  		var el= getEl('option');
		el.textContent = value.title;
		el.value= packageKey;
		addEl(packageDropdown, el);
  	}
    var labelDiv = getEl('div');
    labelDiv.innerText = 'Available Packages (beta)';
    labelDiv.style['font-size'] = '1.2em';
    labelDiv.style['font-weight'] = 'bold';
    addEl(packageDiv, space);
    addEl(packageDiv, labelDiv);
    const pkgHelpLink = getEl('a');
    pkgHelpLink.href = 'https://open-cravat.readthedocs.io/en/latest/Package.html';
    pkgHelpLink.target = '_blank';
    addEl(labelDiv, pkgHelpLink);
    const pkgHelpImg = getEl('img');
    pkgHelpImg.src = '/submit/help.png';
    pkgHelpImg.classList.add('help-img');
    pkgHelpImg.title = 'Packages are groups of annotators, reports, and filters run together. Click for more information.';
    addEl(pkgHelpLink, pkgHelpImg);
    addEl(packageDiv, packageDropdown);
    addEl(packageDiv, space);
    document.querySelector('#show-package').addEventListener('click',event=>{
        packageSelected();
    })
}

function packageSelected() {
    document.getElementById('annotchoosediv').style.display = 'none';
    document.getElementById('divbanner-annot').style['background-color'] = '#3175b0';
    document.getElementById('packagechoosediv').style.display = '';
    document.getElementById('divbanner-pkg').style['background-color'] = 'transparent';
}

function annotatorSelected() {
    document.getElementById('annotchoosediv').style.display = '';
    document.getElementById('divbanner-annot').style['background-color'] = 'transparent';
    document.getElementById('packagechoosediv').style.display = 'none';
    document.getElementById('divbanner-pkg').style['background-color'] = '#3175b0';
}

function buildAnnotatorsSelector () {
    var annotCheckDiv = document.getElementById('annotator-select-div');
    var annotators = OC.GLOBALS.annotators;
    var annotInfos = Object.values(annotators);
    var groupNames = Object.keys(OC.installedGroups);
    for (var i = 0; i < groupNames.length; i++) {
        var name = groupNames[i];
        var module = OC.localModuleInfo[name];
        if (module == undefined) {
            continue;
        }
        var title = module.title;
        annotInfos.push({
            'name': name, 
            'title': title, 
            'type': module.type, 
            'groups': module['groups']
        });
    }
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
        var module = OC.localModuleInfo[annotInfo.name];
        var kind = null;
        if (module.type == 'annotator') {
            kind = 'module';
        } else if (module.type == 'group') {
            kind = 'group';
        }
        checkDatas.push({
            name: annotInfo.name,
            value: annotInfo.name,
            label: annotInfo.title,
            type: annotInfo.type,
            checked: false,
            kind: kind,
            groups: module['groups'],
        })
    }
    buildCheckBoxGroup(checkDatas, annotCheckDiv);
    document.querySelector('#show-annotator').addEventListener('click',event=>{
        annotatorSelected();
    })
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
        var span = getEl('span');
        span.classList.add('checkbox-group-all-button');
        span.addEventListener('click', function (evt) {
            checkBoxGroupAllNoneHandler (evt);
        });
        addEl(allNoneDiv, span);
        var span = getEl('span');
        span.classList.add('checkbox-group-none-button');
        span.addEventListener('click', function (evt) {
            checkBoxGroupAllNoneHandler (evt);
        });
        addEl(allNoneDiv, span);
    }
    // flexbox
    var flexbox = getEl('div');
    addEl(parentDiv, flexbox);
    flexbox.classList.add('checkbox-group-flexbox');
    var checkDivs = [];
    // checks
    var checkDivsForGroup = {};
    for (let i=0; i<checkDatas.length; i++) {
        var checkData = checkDatas[i];
        var checkDiv = getEl('div');
        checkDiv.classList.add('checkbox-group-element');
        checkDiv.classList.add('hide');
        checkDiv.setAttribute('name', checkData.name);
        checkDiv.setAttribute('kind', checkData.kind);
        var mouseoverTimer = null;
        checkDiv.addEventListener('contextmenu', function (evt) {
            mouseoverTimer = setTimeout(function () {
                var dialog = makeModuleDetailDialog(
                    evt.target.closest('.checkbox-group-element').getAttribute('name'), null, null
                )
                dialog.style.width = 'calc(100% - 500px)';
                dialog.style.left = '425px';
                dialog.style.right = 'inherit';
                addEl(document.querySelector('#submitdiv'), dialog);
            }, 500)
            evt.preventDefault();
        })
        checkDiv.addEventListener('mouseout', function (evt) {
            clearTimeout(mouseoverTimer)
        })
        if (checkData.groups != null) {
            var groups = checkData.groups;
            var group = groups[0];
            if (OC.localModuleInfo[group] != undefined) {
                if (checkDivsForGroup[group] == undefined) {
                    checkDivsForGroup[group] = [];
                }
                checkDivsForGroup[group].push(checkDiv);
            } else {
                addEl(flexbox, checkDiv);
            }
        } else {
            addEl(flexbox, checkDiv);
        }
        var label = getEl('label');
        label.classList.add('checkbox-container');
        label.textContent = checkData.label + ' ';
        label.title = 'Right-click to see details.';
        var check = getEl('input');
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
        var span = getEl('span');
        span.className = 'checkmark';
        span.setAttribute('module', checkData.value);
        if (checkData.type == 'group') {
            var t = getEl('span');
            t.textContent = checkData.label + ' ';
            t.style.marginLeft = '9px';
            t.style.cursor = 'default';
            t.addEventListener('click', function (evt) {
                var btn = evt.target.previousSibling;
                var state = btn.getAttribute('state');
                var name = btn.getAttribute('name');
                var text = null;
                var grpDiv = document.querySelector('div.checkbox-group-element-sdiv[name=' + name + ']');
                if (state == 'collapsed') {
                    state = 'expanded';
                    text = '\u25BE';
                    grpDiv.classList.add('on');
                    grpDiv.classList.remove('off');
                } else {
                    state = 'collapsed';
                    text = '\u25B8';
                    grpDiv.classList.add('off');
                    grpDiv.classList.remove('on');
                }
                btn.setAttribute('state', state);
                btn.textContent = text;
            });
            var btn = getEl('span');
            btn.className = 'icon';
            btn.textContent = '\u25B8';
            btn.style.cursor = 'default';
            btn.setAttribute('state', 'collapsed');
            btn.setAttribute('name', checkData.name);
            btn.addEventListener('click', function (evt) {
                var btn = evt.target;
                var state = btn.getAttribute('state');
                var name = btn.getAttribute('name');
                var text = null;
                var grpDiv = document.querySelector('div.checkbox-group-element-sdiv[name=' + name + ']');
                if (state == 'collapsed') {
                    state = 'expanded';
                    text = '\u25BE';
                    grpDiv.classList.add('on');
                    grpDiv.classList.remove('off');
                } else {
                    state = 'collapsed';
                    text = '\u25B8';
                    grpDiv.classList.add('off');
                    grpDiv.classList.remove('on');
                }
                btn.setAttribute('state', state);
                btn.textContent = text;
            });
            addEl(checkDiv, btn);
            addEl(checkDiv, t);
            var sdiv = getEl('div');
            sdiv.id = 'submit-annotator-group-sdiv-' + checkData.name;
            sdiv.classList.add('checkbox-group-element-sdiv');
            sdiv.setAttribute('kind', 'annotator-group-div');
            sdiv.setAttribute('name', checkData.name);
            addEl(checkDiv, sdiv);
        } else {
            addEl(checkDiv, label);
            addEl(label, check);
            addEl(label, span);
            //addEl(checkDiv, sp);
        }
        checkDivs.push(checkDiv);
    }
    var groups = Object.keys(checkDivsForGroup);
    for (var i = 0; i < groups.length; i++) {
        var group = groups[i];
        var sdiv = $('div[kind=annotator-group-div][name=' + group + ']')[0];
        if (sdiv == undefined) {
            continue;
        }
        var checkDivs = checkDivsForGroup[group];
        for (var j = 0; j < checkDivs.length; j++) {
            var checkDiv = checkDivs[j];
            checkDiv.style.width = '100%';
            addEl(sdiv, checkDiv);
        }
    }
    $('div[kind=annotator-group-div]').each(function () {
        var name = this.getAttribute('name');
        var height = this.clientHeight;
        var divid = '#submit-annotator-group-sdiv-' + name;
        var stylesheets = window.document.styleSheets;
        for (var i = 0; i <= stylesheets.length; i++) {
            var stylesheet = stylesheets[i];
            if (stylesheet.href.indexOf('websubmit.css') >= 0) {
                //stylesheet.insertRule(divid + ' {overflow: hidden; width: 99%; transition: max-height .4s; max-height: ' + height + 'px;}');
                stylesheet.insertRule(divid + ' {overflow: hidden; width: 99%; transition: max-height .4s; max-height: inherit;}');
                stylesheet.insertRule(divid + '.off {overflow: hidden; max-height: 0px;}');
                stylesheet.insertRule(divid + '.on {overflow: hidden; border: 1px dotted #aaaaaa;}');
                break;
            }
        }
        this.classList.add('off');
    });
    return parentDiv;
}

function onChangeAnnotatorGroupCheckbox (tags) {
    var $moduleCheckboxes = $('div.checkbox-group-element[kind=module],div.checkbox-group-element[kind=group]');
    var $selectCheckbox = $('div.checkbox-group-element[kind=collect] input:checked');
    var idx = tags.indexOf('selected');
    var selectChecked = idx >= 0;
    if (selectChecked) {
        tags.splice(idx, 1);
    }
    var $groupCheckboxes = $('div.checkbox-group-element[kind=tag] input:checked,div.checkbox-group-element[kind=group] input:checked');
    if (tags.length == 0) {
        if (selectChecked) {
            $moduleCheckboxes.addClass('hide').removeClass('show');
            $moduleCheckboxes.each(function () {
                if (this.querySelector('input').checked == true) {
                    this.classList.add('show');
                    this.classList.remove('hide');
                }
            });
        } else {
            $moduleCheckboxes.addClass('hide').removeClass('show');
        }
    } else {
        $moduleCheckboxes.addClass('hide').removeClass('show');
        var localModules = Object.keys(OC.localModuleInfo);
        for (var j = 0; j < tags.length; j++) {
            var tag = tags[j];
            for (var i = 0; i < localModules.length; i++) {
                var module = OC.localModuleInfo[localModules[i]];
                var c = $('div.checkbox-group-element[kind=module][name=' + module.name + '],div.checkbox-group-element[kind=group][name=' + module.name + ']')[0];
                if (c != undefined) {
                    if (module.tags.indexOf(tag) >= 0) {
                        if (selectChecked) {
                            if (c.querySelector('input').checked == true) {
                                c.classList.add('show');
                                c.classList.remove('hide');
                            }
                        } else {
                            c.classList.add('show');
                            c.classList.remove('hide');
                            var groups = OC.localModuleInfo[c.getAttribute('name')].groups;
                            for (var groupNo = 0; groupNo < groups.length; groupNo++) {
                                var group = groups[groupNo];
                                var groupDiv = document.querySelector('div.checkbox-group-element[name="'+group+'"]');
                                groupDiv.classList.add('show');
                                groupDiv.classList.remove('hide');
                            }
                        }
                    }
                }
            }
        }
    }
    if ( ! checkVisible(document.querySelector('#annotator-select-div').querySelector('.checkbox-group-flexbox'))) {
        document.querySelector('#annotchoosediv').scrollIntoView();
    }
}

function checkBoxGroupAllNoneHandler (event) {
    var $elem = $(event.target);
    let checked;
    if ($elem.hasClass('checkbox-group-all-button')) {
        checked = true;
    } else {
        checked = false;
    }
    $elem.parent().siblings('.checkbox-group-flexbox').children('.checkbox-group-element.show').each(function (i, elem) {
        $(elem).find('input').prop('checked', checked);
    });
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


function openSubmitDiv () {
    var div = document.getElementById('submitcontentdiv');
    div.style.display = 'block';
}

function getServermode () {
    $.ajax({
        url: '/submit/servermode',
        type: 'get',
        success: function (response) {
            OC.servermode = response['servermode'];
            if (OC.servermode == false) {
                setupNoServerMode();
            } else {
                setupServerMode();
            }
        },
        complete: function(response) {
            requestUserEmail();
        }
    });
}

function setupNoServerMode () {
    setLastAssembly();
}

function setupServerMode () {
    $('head').append('<link rel="stylesheet" type="text/css" href="/server/nocache/cravat_multiuser.css">');
    import('/server/nocache/cravat_multiuser_module.js').then((multiuser) => {
        multiuser.checkLogged(OC.username);
    });
    document.getElementById('settingsdiv').style.display = 'none';
    document.querySelector('.threedotsdiv').style.display = 'none';
    $.ajax({
        url: '/server/usersettings',
        type: 'get',
        success: function (response) {
            OC.GLOBALS.usersettings = response;
            setLastAssembly();
        }
    });
}

function populatePackageVersions () {
    $.get('/submit/reports').done(function(data) {
        OC.GLOBALS.reports = data;
        $.get('/submit/packageversions').done(function(data){
            OC.systemReadyObj.online = data.latest != null
            if (OC.systemReadyObj.online == false) {
                document.querySelector('#nointernetdiv').style.display = 'block';
            }
            var curverspans = document.getElementsByClassName('curverspan');
            for (var i = 0; i < curverspans.length; i++) {
                var curverspan = curverspans[i];
                var s = getEl('span');
                s.textContent = data.current;
                addEl(curverspan, s);
                if (data.update) {
                    s.textContent = s.textContent + '\xa0';
                    var a = getEl('a');
                    a.href = 'https://open-cravat.readthedocs.io/en/latest/Update-Instructions.html';
                    a.target = '_blank';
                    //a.textContent = '(' + data.latest + ')';
                    a.textContent = 'new release available';
                    a.style.color = 'red';
                    addEl(curverspan, a);
                }
            }
            // getRemote();
            OC.mediator.publish('getRemote');
        });
    });
}

function onClickInputTextArea () {
    let input = document.getElementById('input-text');
    input.classList.add('input-text-selected')
}

function onBlurInputTextArea () {
    let input = document.getElementById('input-text');
    input.classList.remove('input-text-selected')
}

function resizePage () {
    var div = document.getElementById('submit-form');
    var h = window.innerHeight - 148;
    div.style.height = h + 'px';
    var div = document.getElementById('jobdiv');
    var h = window.innerHeight - 85;
    div.style.height = h + 'px';
}

function clearInputFiles () {
    OC.inputFileList = [];
    document.querySelector('#mult-inputs-message').style.display = 'none';
    document.querySelector('#clear_inputfilelist_button').style.display = 'none';
    $('#mult-inputs-list').empty();
}

function populateMultInputsMessage() {
    var fileInputElem = document.getElementById('input-file');
    var files = fileInputElem.files;
    if (files.length >= 1) {
        $('#mult-inputs-message').css('display','block');
        var $fileListDiv = $('#mult-inputs-list');
        for (var i=0; i<files.length; i++) {
            var file = files[i];
            if (OC.inputFileList.indexOf(file.name) == -1) {
                var sdiv = getEl('div');
                var span = getEl('span');
                span.textContent = file.name;
                addEl(sdiv, span);
                var minus = getEl('button');
                minus.classList.add('butn');
                minus.classList.add('fileaddbutn');
                minus.textContent = 'X';
                minus.title = 'Click to remove the file.';
                minus.addEventListener('click', function (evt) {
                    var fileName = evt.target.previousSibling.textContent;
                    for (var j = 0; j < OC.inputFileList.length; j++) {
                        if (OC.inputFileList[j].name == fileName) {
                            OC.inputFileList.splice(j, 1);
                            break;
                        }
                    }
                    evt.target.parentElement.parentElement.removeChild(evt.target.parentElement);
                    if (OC.inputFileList.length == 0) {
                        document.querySelector('#mult-inputs-message').style.display = 'none';
                        document.querySelector('#clear_inputfilelist_button').style.display = 'none';
                    }
                });
                addEl(sdiv, minus);
                $fileListDiv.append($(sdiv));
                OC.inputFileList.push(file);
            }
        }
    }
    if (OC.inputFileList.length > 0) {
        document.querySelector('#clear_inputfilelist_button').style.display = 'inline-block';
        document.querySelector('#mult-inputs-message').style.display = 'block';
    } else {
        document.querySelector('#clear_inputfilelist_button').style.display = 'none';
        document.querySelector('#mult-inputs-message').style.display = 'none';
    }
    document.querySelector('#input-file').value = '';
}

function closeUserEmailRequestModal() {
    document.getElementById('user-email-request-div').style.display = 'none';
}

function handleUserEmailOptOutClick() {
    const optOut = document.getElementById('user-email-opt-out').checked;
    if (optOut) {
        document.getElementById('user-email').value = '';
        document.getElementById('user-email').disabled = true;
        document.getElementById('user-email-error').style.display = 'none';
    } else {
        document.getElementById('user-email').disabled = false;
    }
}

function submitUserEmailRequest() {
    const email = document.getElementById('user-email').value;
    const emailOptOut = document.getElementById('user-email-opt-out').checked;
    // validate
    if (!emailOptOut) {
        if (!email || email.indexOf('@') < 0) {
            document.getElementById('user-email-error').style.display = 'flex';
            return;
        }
    }

    // TODO: refactor to combine with header.js > updateSystemConf()
     $.get('/submit/getsystemconfinfo').done(function (response) {
        var optout = response['content']['save_metrics'];

        response['content']['user_email'] = email;
        response['content']['user_email_opt_out'] = emailOptOut;
        $.ajax({
            url:'/submit/updatesystemconf',
            data: {'sysconf': JSON.stringify(response['content']), 'optout': optout},
            type: 'GET',
            success: function (response) {
                closeUserEmailRequestModal();
                if (response['success'] == true) {
                    const mdiv = getEl('div');
                    const span = getEl('span');
                    span.textContent = 'User Email configuration has been updated.';
                    addEl(mdiv, span);
                    addEl(mdiv, getEl('br'));
                    addEl(mdiv, getEl('br'));
                    const justOk = true;
                    OC.mediator.publish('showyesnodialog', mdiv, null, false, justOk);
                } else {
                    const mdiv = getEl('div');
                    const span = getEl('span');
                    span.textContent = 'User Email configuration was not successful';
                    addEl(mdiv, span);
                    addEl(mdiv, getEl('br'));
                    addEl(mdiv, getEl('br'));
                    const msg = getEl('span');
                    msg.textContent = response['msg'];
                    addEl(mdiv, msg);
                    addEl(mdiv, getEl('br'));
                    addEl(mdiv, getEl('br'));
                    const justOk = true;
                    OC.mediator.publish('showyesnodialog', mdiv, null, false, justOk);
                    return;
                }
            }
        });
    });
}

//TODO: change the event listeners that talk between pages to use the mediator
function addListeners () {
    addMediatorListeners();

    // index.html handlers
    $('#clear_inputfilelist_button').on('click', onClearInputFileList);
    $('#input-text')
        .on('click', onClickInputTextArea)
        .on('blur', onBlurInputTextArea);
    $('#jobs-table-pagination-prev-button').on('click', onClickJobsListPrevPage);
    $('#jobs-table-pagination-next-button').on('click', onClickJobsListNextPage);
    $('#job-import-file').on('change', importJob);
    $('#report_generation_generate_button').on('click', createJobReport);
    $('#report_generation_close_button').on('click', closeReportGenerationDiv);

    $('#submit-job-button').click(submit);
    $('#input-text').change(inputChangeHandler);
    $('#input-file').change(inputChangeHandler);
    $('#all-annotators-button').click(allNoAnnotatorsHandler);
    $('#no-annotators-button').click(allNoAnnotatorsHandler);
    $('.input-example-button').click(inputExampleChangeHandler)
    $('#refresh-jobs-table-btn').click(refreshJobsTable);
    $('.jobsdirinput').change(setJobsDir);
    $('#chaticondiv').click(toggleChatBox)

    // User Request Modal
    $('#user-email-opt-out').change(handleUserEmailOptOutClick);
    $('#submit-user-email-request').click(submitUserEmailRequest);
    document.getElementById('user-email-request-modal-close').addEventListener('click', closeUserEmailRequestModal);
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
            OC.storeModuleDivClicked = false;
        } else {
            OC.storeModuleDivClicked = true;
        }
        if (evt.target.id != 'settingsdots' && evt.target.id != 'settingsdiv' && evt.target.classList.contains('settingsdiv-elem') == false) {
            var div = document.getElementById('settingsdiv');
            if (div != null) {
                div.style.display = 'none';
            }
        }
        if (evt.target.id != 'help-menu-button' && evt.target.id != 'helpdiv' && evt.target.classList.contains('help-link') === false) {
            let helpDiv = document.getElementById('helpdiv');
            if (helpDiv) {
                helpDiv.style.display = 'none';
            }
        }
        if (evt.target.id == 'report_generation_generate_button') {
            createJobReport(evt);
        } else if (evt.target.id == 'report_generation_close_button') {
            closeReportGenerationDiv();
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
        if (OC.storeModuleDivClicked) {
            var k = evt.key;
            var moduleDiv = document.getElementById('moduledetaildiv_store');
            var moduleListName = moduleDiv.getAttribute('modulelistname');
            var moduleListPos = moduleDiv.getAttribute('modulelistpos');
            var moduleList = OC.moduleLists[moduleListName];
            if (k == 'ArrowRight') {
                moduleListPos++;
                if (moduleListPos >= moduleList.length) {
                    moduleListPos = 0;
                }
                var moduleName = moduleList[moduleListPos];
                makeModuleDetailDialog(moduleName, moduleListName, moduleListPos);
                evt.stopPropagation();
            } else if (k == 'ArrowLeft') {
                moduleListPos--;
                if (moduleListPos < 0) {
                    moduleListPos = moduleList.length - 1;
                }
                var moduleName = moduleList[moduleListPos];
                makeModuleDetailDialog(moduleName, moduleListName, moduleListPos);
                evt.stopPropagation();
            }
        }
    });
}

function addMediatorListeners() {
    OC.mediator.subscribe('navigate', changePage);
    OC.mediator.subscribe('populateJobs', populateJobs);
    OC.mediator.subscribe('moduleinfo.annotators', buildAnnotatorsSelector);
    OC.mediator.subscribe('setupJobs', handleSetupJobsTab);
    OC.mediator.subscribe('moduleinfo.local', setVariantReportURL)
}

function requestUserEmail() {
    if (OC.servermode) { return; }
    $.get('/submit/getsystemconfinfo').done(function (response) {
        const emailOptOut = response['content']['user_email_opt_out'];
        const email= response['content']['user_email'];
        if (!emailOptOut && !email) {
            document.getElementById('user-email-request-div').style.display = 'flex';
        }
    });
}

function setVariantReportURL() {
    let url = '/webapps/variantreport/index.html'
    if (!('variantreport' in OC.localModuleInfo)) {
        url = 'https://run.opencravat.org'+url
    }
    let tabhead = document.querySelector('#singlevar_tabhead');
    tabhead.setAttribute("onclick", `window.open('${url}', '_blank')`);
    tabhead.setAttribute("disabled","f");
}

function setLastAssembly () {
    let sel = document.getElementById('assembly-select');
    if (!OC.servermode) {
        $.ajax({
            url: '/submit/lastassembly',
            ajax: true,
            success: function (response) {
                sel.value = response;
            },
        });
    } else {
        if (OC.GLOBALS.usersettings.hasOwnProperty('lastAssembly')) {
            sel.value = OC.GLOBALS.usersettings.lastAssembly;
        } else {
            sel.value = null;
        }
    }
}

function getJobById (jobId) {
    return OC.GLOBALS.idToJob[jobId];
}

function updateRunningJobTrs (job) {
    var idx = OC.GLOBALS.jobs.indexOf(job.id);
    if (idx < OC.jobsListCurStart || idx >= OC.jobsListCurEnd) {
        return;
    }
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

function onClearInputFileList () {
    document.querySelector('#clear_inputfilelist_button').style.display = 'none';
    document.querySelector('#mult-inputs-message').style.display = 'none';
    $(document.querySelector('#mult-inputs-list')).empty();
    document.querySelector('#input-file').value = '';
    OC.inputFileList = [];
}

function populateInputFormats () {
    let inputSel = $('#submit-input-format-select');
    inputSel.prop('disabled',true);
    for (let moduleName in OC.localModuleInfo) {
        if (moduleName.endsWith('-converter')) {
            let inputName = moduleName.split('-')[0];
            let opt = $(getEl('option'))
                .val(inputName)
                .text(inputName);
            inputSel.append(opt);
        }
    }
    inputSel.prop('disabled',false);
}

function websubmit_run () {
    hideSpinner();
    hideUpdateRemoteSpinner();
    var urlParams = new URLSearchParams(window.location.search);
    OC.username = urlParams.get('username');
    getServermode();
    connectWebSocket();
    checkConnection();
    populatePackageVersions();
    getBaseModuleNames();
    addListeners();
    loadSystemConf();
    populateMultInputsMessage();
};

function importJob() {
    let fileSel = document.querySelector('#job-import-file');
    if (fileSel.files.length === 0) return;
    var req = new XMLHttpRequest();
    req.open('POST', '/submit/import');
    req.setRequestHeader('Content-Disposition', `attachment; filename=${fileSel.files[0].name}`);
    req.upload.onprogress = function (evt) {
        var uploadPerc = evt.loaded / evt.total * 100;
        document.querySelector('#spinner-div-progress-bar').style.width = uploadPerc + '%';
        document.querySelector('#spinner-div-progress-num').textContent = uploadPerc.toFixed(0) + '%';
    };
    req.onloadend  = function (evt) {
        hideSpinner();
        refreshJobsTable();
    };
    showSpinner();
    req.send(fileSel.files[0]);
}

// Additional analysis stuff. Currently just casecontrol. Design expected to change when more added.
const addtlAnalysis = {
    names: [],
    fetchers: {},
};

function populateAddtlAnalysis () {
    let display = false;
    let addtlWrapper = $('#addtl-analysis-content');
    addtlWrapper.empty();
    display = display || populateCaseControl(addtlWrapper)===true;
    if (display) {
        $('#addtl-analysis-div').css('display','');
    }
}

/***
 * Mediator handler called by setupJobsTab() from webstore.js
 */
function handleSetupJobsTab() {
        populateInputFormats();
    buildAnnotatorGroupSelector();
    let annotatorsDone = populateAnnotators();
    let packagesDone = populatePackages();
    annotatorsDone.then(() => {
        // Populate cc here to avoid it showing before annotators
        // and then getting quickly shoved down. Looks bad.
        populateAddtlAnalysis();
    });
}

function populateCaseControl (outer) {
    if ( ! OC.localModuleInfo.hasOwnProperty('casecontrol')) {
        return false
    }
    let wrapper = $(getEl('div'))
        .attr('id','case-control-wrapper')
        .addClass('addtl-analysis-wrapper')
    outer.append(wrapper);
    let d1 = $(getEl('div'));
    wrapper.append(d1);
    let cohortsInput = $(getEl('input'))
        .attr('id','case-control-cohorts')
        .attr('type','file')
        .css('display','none');
    d1.append(cohortsInput);
    let cohortsLabel = $(getEl('label'))
        .attr('for','case-control-cohorts')
        .text('Case-Control cohorts')
        .attr('title','Compare variant distribution across case and control cohorts. See documentation for details.');
    d1.append(cohortsLabel);
    let helpIcon = $(getEl('a'))
        .attr('id','case-control-help')
        .attr('target','_blank')
        .attr('href','https://open-cravat.readthedocs.io/en/latest/Case-Control.html')
        .append($(getEl('img')).attr('src','../help.png').attr('class','help-img'));
    d1.append(helpIcon);
    let d2 = $(getEl('div'))
    wrapper.append(d2);
    let spanDefaultText = 'No file selected'
    let filenameSpan = $(getEl('span'))
        .attr('id','case-control-filename')
        .text(spanDefaultText);
    d2.append(filenameSpan);
    let clearBtn = $(getEl('button'))
        .click(event => {
            cohortsInput.val('').trigger('change');
        })
        .text('X')
        .addClass('butn')
        .css('display','none');
    d2.append(clearBtn);
    cohortsInput.change(event => {
        let files = event.target.files;
        if (files.length > 0) {
            filenameSpan.text(files[0].name);
            clearBtn.css('display','');
        } else {
            filenameSpan.text(spanDefaultText);
            clearBtn.css('display','none');
        }
    })
    addtlAnalysis.names.push('casecontrol');
    addtlAnalysis.fetchers.casecontrol = function () {
        let files = cohortsInput[0].files;
        if (files.length > 0) {
            return files[0];
        }
    }    
    return true
}

export { websubmit_run };
