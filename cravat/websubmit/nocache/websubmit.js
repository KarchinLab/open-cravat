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
    usersettings: {},
}
var currentTab = 'submit';
var websubmitReportBeingGenerated = {};
var jobRunning = {};
var tagsCollectedForSubmit = [];
var jobsPerPageInList = 15;
var jobsListCurStart = 0;
var jobsListCurEnd = jobsPerPageInList;
var systemReadyObj = {};
var formData = null;
var adminMode = false;
var inputFileList = [];
var JOB_IDS = []
var jobListUpdateIntervalFn = null;
var reportRunning = {};
var systemConf;

function submit () {
    if (servermode && logged == false) {
        alert('Log in before submitting a job.');
        return;
    }
    formData = new FormData();
    var textInputElem = $('#input-text');
    var textVal = textInputElem.val();
    let inputFiles = [];
    if (textVal.length > 0) {
        var textBlob = new Blob([textVal], {type:'text/plain'})
        inputFiles.push(new File([textBlob], 'input'));
    } else {
        inputFiles = inputFileList;
    }
    if (inputFiles.length === 0) {
        alert('Choose a input variant files, enter variants, or click an input example button.');
        return;
    }
    for (var i=0; i<inputFiles.length; i++) {
        formData.append('file_'+i,inputFiles[i]);
    }
    var submitOpts = {
        annotators: [],
        reports: []
    }
    var annotChecks = $('#annotator-select-div').find('input[type=checkbox][kind=module]');
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
    var assmSelect = $('#assembly-select');
    var assembly = assmSelect.val();
    if (assembly !== null) {
        submitOpts.assembly = assembly;
    } else {
        showYesNoDialog('Please select a genome version', ()=>{
            $('#assembly-select-div').css('border', '2px solid red');
            setTimeout(()=>{$('#assembly-select-div').css('border', 'none');},2000);
        }, false, true);
        return;
    }
    submitOpts.forcedinputformat = $('#submit-input-format-select').val();
    var note = document.getElementById('jobnoteinput').value;
    submitOpts.note = note;
    document.querySelector('#submit-job-button').disabled = true;
    formData.append('options',JSON.stringify(submitOpts));
    // AddtlAnalysis
    for (addtlName of addtlAnalysis.names) {
        let addtlData = addtlAnalysis.fetchers[addtlName]();
        if (addtlData != undefined) {
            formData.append(addtlName, addtlAnalysis.fetchers[addtlName]());
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
        addEl(alertDiv,getEl('br'));
        var span = getEl('span');
        span.textContent = 'The limit can be changed at the settings menu.';
        addEl(alertDiv, span);
        addEl(alertDiv,getEl('br'));
        showYesNoDialog(alertDiv, enableSubmitButton, false, true);
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
                    submittedJobs.push(response);
                    addJob(response, true);
                    //sortJobs();
                    buildJobsTable();
                }
                if (response.expected_runtime > 0) {
                }
                jobRunning[response['id']] = true;
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
                span.innerHTML = 'If you think this was caused by an error, <a href="mailto:support@cravat.us">let us know</a>'
                addEl(alertDiv,span);
                addEl(alertDiv,getEl('br'));
                addEl(alertDiv,getEl('br'));
                var span = getEl('span');
                span.innerText = 'Details: '+response.msg;
                addEl(alertDiv,span);
                showYesNoDialog(alertDiv, null, false, true);

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
        req.send(formData);
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

function addJob (job, prepend) {
    var trueDate = new Date(job.submission_time);
    job.submission_time = trueDate;
    if (GLOBALS.jobs.indexOf(job.id) == -1) {
        if (prepend == true) {
            GLOBALS.jobs.unshift(job.id);
        } else {
            GLOBALS.jobs.push(job.id);
        }
    }
    GLOBALS.idToJob[job.id] = job;
    var status = job.status;
    if (status != 'Finished' && status != 'Error' && status != 'Aborted') {
        jobRunning[job.id] = true;
    } else if (jobRunning[job.id] != undefined) {
        delete jobRunning[job.id];
    }
    if (job.reports_being_generated.length > 0) {
        websubmitReportBeingGenerated[job.id] = {};
        if (reportRunning[job.id] == undefined) {
            reportRunning[job.id] = {};
        }
        for (var i = 0; i < job.reports_being_generated.length; i++) {
            var reportType = job.reports_being_generated[i];
            websubmitReportBeingGenerated[job.id][reportType] = true;
            reportRunning[job.id][reportType] = true;
        }
    }
}

function createJobReport (evt) {
    var div = document.querySelector('#report_generation_div');
    var jobId = div.getAttribute('jobid');
    closeReportGenerationDiv();
    var select = document.querySelector('#report_generation_div_select');
    var reportType = select.value;
    if (websubmitReportBeingGenerated[jobId] == undefined) {
        websubmitReportBeingGenerated[jobId] = {};
    }
    websubmitReportBeingGenerated[jobId][reportType] = true;
    buildJobsTable();
    generateReport(jobId, reportType, function () {
        if (websubmitReportBeingGenerated[jobId] == undefined) {
            delete websubmitReportBeingGenerated[jobId];
        } else {
            //websubmitReportBeingGenerated[jobId][reportType] = false;
            delete websubmitReportBeingGenerated[jobId][reportType];
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
                showYesNoDialog(mdiv, null, false, true);
            }
            callback();
        }
    });
    if (reportRunning[jobId] == undefined) {
        reportRunning[jobId] = {};
    }
    reportRunning[jobId][reportType] = true;
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
    // Username 
    if (adminMode == true) {
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
        viewTd.textContent = statusC;
    }
    addEl(jobTr, viewTd);
    var dbTd = getEl('td');
    dbTd.style.textAlign = 'center';
    // Reports
    for (var i = 0; i < GLOBALS.reports.valid.length; i++) {
        var reportType = GLOBALS.reports.valid[i];
        if ((websubmitReportBeingGenerated[job.id] != undefined && websubmitReportBeingGenerated[job.id][reportType] == true) || job.reports_being_generated.includes(reportType)) {
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
                btn.title = 'Click to download.';
                if (job.status == 'Finished') {
                    addEl(dbTd, btn);
                }
            }
        }
    }
    // Log
    var logLink = getEl('a');
    logLink.setAttribute('href','/submit/jobs/' + job.id + '/log');
    logLink.setAttribute('target', '_blank');
    logLink.setAttribute('title', 'Click to download.');
    var button = getEl('button');
    button.classList.add('butn');
    button.classList.add('active-download-button');
    addEl(button, getTn('Log'));
    addEl(logLink, button);
    addEl(dbTd, logLink);
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
        var job = GLOBALS.idToJob[jobId];
        var select = document.querySelector('#report_generation_div_select');
        while (select.options.length > 0) {
            select.remove(0);
        }
        for (var i = 0; i < GLOBALS.reports.valid.length; i++) {
            var reportType = GLOBALS.reports.valid[i];
            if ((websubmitReportBeingGenerated[job.id] != undefined && websubmitReportBeingGenerated[job.id][reportType] == true) || job.reports.includes(reportType) == true) {
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
    if (job.db_path != undefined && job.db_path != '') {
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
    var headerTr = document.querySelector('#jobs-table thead tr');
    if (adminMode == true) {
        var firstTd = headerTr.firstChild;
        if (firstTd.textContent != 'User') {
            var td = getEl('th');
            td.textContent = 'User';
            headerTr.prepend(td);
        }
    }
    var jobsTable = document.querySelector('#jobs-table tbody');
    $(jobsTable).empty();
    fillJobTable(allJobs, jobsListCurStart, jobsListCurEnd, jobsTable);
}

function fillJobTable (allJobs, start, end, jobsTable) {
    for (let i = start; i < Math.min(end, allJobs.length); i++) {
        job = GLOBALS.idToJob[allJobs[i]];
        if (job == undefined) {
            continue;
        }
        ji = job.id;
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
    jobsListCurEnd -= jobsPerPageInList;
    if (jobsListCurEnd < jobsPerPageInList) {
        jobsListCurEnd = jobsPerPageInList;
    }
    jobsListCurStart = jobsListCurEnd - jobsPerPageInList;
    jobsListCurStart = Math.min(Math.max(0, jobsListCurStart), GLOBALS.jobs.length);
    jobsListCurEnd = Math.max(0, Math.min(jobsListCurEnd, GLOBALS.jobs.length));
    showJobListPage();
}

function onClickJobsListNextPage () {
    jobsListCurStart += jobsPerPageInList;
    if (jobsListCurStart >= GLOBALS.jobs.length) {
        jobsListCurStart = GLOBALS.jobs.length - (GLOBALS.jobs.length % jobsPerPageInList);
    }
    jobsListCurEnd = jobsListCurStart + jobsPerPageInList;
    jobsListCurStart = Math.min(Math.max(0, jobsListCurStart), GLOBALS.jobs.length);
    jobsListCurEnd = Math.max(0, Math.min(jobsListCurEnd, GLOBALS.jobs.length));
    showJobListPage();
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

function jobReportDownloadButtonHandler (evt) {
    var btn = evt.target;
    var jobId = btn.getAttribute('jobid');
    var reportType = btn.getAttribute('report-type');
    downloadReport(jobId, reportType);
}

function downloadReport (jobId, reportType) {
    url = '/submit/jobs/'+jobId+'/reports/'+reportType;
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
    assembly = assembly === null ? 'hg38' : assembly;
    var formatAssembly = format + '.' + assembly;
    var getExampleText = new Promise((resolve, reject) => {
        var cachedText = GLOBALS.inputExamples[formatAssembly];
        if (cachedText === undefined) {
            var fname = formatAssembly + '.txt';
            $.ajax({
                url:'/submit/input-examples/'+fname,
                type: 'GET',
                contentType: 'application/json',
                success: function (data) {
                    clearInputFiles();
                    document.querySelector('#input-file').value = '';
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

function showJobListPage () {
    var jis = GLOBALS.jobs.slice(jobsListCurStart, jobsListCurEnd);
    $.ajax({
        url: '/submit/getjobs',
        data: {'ids': JSON.stringify(jis)},
        success: function (response) {
            for (var i=0; i < response.length; i++) {
                var job = response[i];
                addJob(job);
            }
            buildJobsTable();
            if (jobListUpdateIntervalFn == null) {
                jobListUpdateIntervalFn = setInterval(function () {
                    var runningJobIds = Object.keys(jobRunning);
                    var runningReportIds = Object.keys(reportRunning);
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
                                    GLOBALS.idToJob[job.id] = job;
                                    if (job.status == 'Finished' || job.status == 'Aborted' || job.status == 'Error') {
                                        delete jobRunning[job.id];
                                    }
                                    if (reportRunning[job.id] != undefined) {
                                        var reportTypes = Object.keys(reportRunning[job.id]);
                                        for (var j = 0; j < reportTypes.length; j++) {
                                            var reportType = reportTypes[j];
                                            if (job.reports.includes(reportType)) {
                                                delete reportRunning[job.id][reportType];
                                                delete websubmitReportBeingGenerated[job.id][reportType];
                                                if (Object.keys(reportRunning[job.id]).length == 0) {
                                                    delete reportRunning[job.id];
                                                    delete websubmitReportBeingGenerated[job.id];
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
                }, 1000);
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
                GLOBALS.jobs = response;
                jobsListCurStart = 0;
                jobsListCurEnd = jobsListCurStart + jobsPerPageInList;
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

function populateAnnotators () {
    return new Promise((resolve, reject) => {
        $.ajax({
            url:'/submit/annotators',
            type: 'GET',
            success: function (data) {
                GLOBALS.annotators = data
                setTimeout(function () {
                    buildAnnotatorsSelector();
                    resolve();
                }, 100);
            }
        })
    });
}

function titleCase(str) {
    return str.replace(
      /\w\S*/g,
      function(txt) {
        return txt.charAt(0).toUpperCase() + txt.substr(1).toLowerCase();
      }
    );
  }

function buildAnnotatorGroupSelector () {
    tagsCollectedForSubmit = [];
    tagMembership = {};
    for (var module in localModuleInfo) {
        if (localModuleInfo[module].type != 'annotator') {
            continue;
        }
        var tags = localModuleInfo[module].tags;
        for (var i = 0; i < tags.length; i++) {
            var tag = tags[i];
            if (tagsCollectedForSubmit.indexOf(tag) == -1) {
                tagsCollectedForSubmit.push(tag);
                tagMembership[tag] = 1;
            } else {
                tagMembership[tag]++;
            }
        }
    }
    tagsCollectedForSubmit.sort((a,b)=>{return tagMembership[b]-tagMembership[a]});
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
    for (var i = 0; i < tagsCollectedForSubmit.length; i++) {
        var tag = tagsCollectedForSubmit[i];
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
    for (var i = 0; i < tagsCollectedForSubmit.length; i++) {
        var tagName = tagsCollectedForSubmit[i];
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
    for (let tag of tagsCollectedForSubmit) {
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

function buildAnnotatorsSelector () {
    var annotCheckDiv = document.getElementById('annotator-select-div');
    var annotators = GLOBALS.annotators;
    var annotInfos = Object.values(annotators);
    var groupNames = Object.keys(installedGroups);
    for (var i = 0; i < groupNames.length; i++) {
        var name = groupNames[i];
        var module = localModuleInfo[name];
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
        var module = localModuleInfo[annotInfo.name];
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
        checkDiv.addEventListener('mouseover', function (evt) {
            mouseoverTimer = setTimeout(function () {
                var dialog = makeModuleDetailDialog(
                    evt.target.closest('.checkbox-group-element').getAttribute('name'), null, null);
                dialog.style.width = 'calc(100% - 500px)';
                dialog.style.left = '425px';
                dialog.style.right = 'inherit';
                addEl(document.querySelector('#submitdiv'), dialog);
                //evt.preventDefault();
                //evt.stopPropagation();
            }, 500)
        })
        checkDiv.addEventListener('mouseout', function (evt) {
            clearTimeout(mouseoverTimer)
        })
        if (checkData.groups != null) {
            var groups = checkData.groups;
            var group = groups[0];
            if (localModuleInfo[group] != undefined) {
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
        //label.title = checkData.label + '. Right-click to see details.';
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
        var localModules = Object.keys(localModuleInfo);
        for (var j = 0; j < tags.length; j++) {
            var tag = tags[j];
            for (var i = 0; i < localModules.length; i++) {
                var module = localModuleInfo[localModules[i]];
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
                            var groups = localModuleInfo[c.getAttribute('name')].groups;
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

function checkVisible(elm) {
    // https://stackoverflow.com/questions/5353934/check-if-element-is-visible-on-screen
    var rect = elm.getBoundingClientRect();
    var viewHeight = Math.max(document.documentElement.clientHeight, window.innerHeight);
    return !(rect.bottom < 0 || rect.top - viewHeight >= 0);
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
        systemConf = response.content;
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
        var s = document.getElementById('settings_gui_input_size_limit');
        var cutoff = parseInt(response['content']['gui_input_size_limit']);
        s.value = cutoff;
        var s = document.getElementById('settings_max_num_concurrent_jobs');
        s.value = parseInt(response['content']['max_num_concurrent_jobs']);
        var s = document.getElementById('settings_max_num_concurrent_annotators_per_job');
        s.value = parseInt(response['content']['max_num_concurrent_annotators_per_job']);
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
        var s = document.getElementById('settings_gui_input_size_limit');
        response['content']['gui_input_size_limit'] = parseInt(s.value);
        var s = document.getElementById('settings_max_num_concurrent_jobs');
        response['content']['max_num_concurrent_jobs'] = parseInt(s.value);
        var s = document.getElementById('settings_max_num_concurrent_annotators_per_job');
        response['content']['max_num_concurrent_annotators_per_job'] = parseInt(s.value);
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
                    var span = getEl('span');
                    span.textContent = response['msg'];
                    addEl(mdiv, span);
                    addEl(mdiv, getEl('br'));
                    addEl(mdiv, getEl('br'));
                    var justOk = true;
                    showYesNoDialog(mdiv, null, false, justOk);
                    return;
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
    setLastAssembly();
}

function setupServerMode () {
    $('head').append('<link rel="stylesheet" type="text/css" href="/server/nocache/cravat_multiuser.css">');
    $.getScript('/server/nocache/cravat_multiuser.js', function () {
        checkLogged(username)
    });
    document.getElementById('settingsdiv').style.display = 'none';
    document.querySelector('.threedotsdiv').style.display = 'none';
    $.ajax({
        url: '/server/usersettings',
        type: 'get',
        success: function (response) {
            GLOBALS.usersettings = response;
            setLastAssembly();
        }
    });
}

function populatePackageVersions () {
    $.get('/submit/reports').done(function(data) {
        GLOBALS.reports = data;
        $.get('/submit/packageversions').done(function(data){
            systemReadyObj.online = data.latest != null
            if (systemReadyObj.online == false) {
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
                    a.href = 'https://github.com/KarchinLab/open-cravat/wiki/Update-Instructions';
                    a.target = '_blank';
                    //a.textContent = '(' + data.latest + ')';
                    a.textContent = 'new release available';
                    a.style.color = 'red';
                    addEl(curverspan, a);
                }
            }
            getRemote();
        });
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
    var h = window.innerHeight - 148;
    div.style.height = h + 'px';
    var div = document.getElementById('jobdiv');
    var h = window.innerHeight - 85;
    div.style.height = h + 'px';
}

function clearInputFiles () {
    inputFileList = [];
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
            if (file.name.indexOf(' ') > -1) {
                var alertDiv = getEl('div');
                var span = getEl('span');
                span.textContent = 'Space in file names is not allowed.';
                addEl(alertDiv, span);
                showYesNoDialog(alertDiv, null, false, true);
                return;
            }
            if (inputFileList.indexOf(file.name) == -1) {
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
                    for (var j = 0; j < inputFileList.length; j++) {
                        if (inputFileList[j].name == fileName) {
                            inputFileList.splice(j, 1);
                            break;
                        }
                    }
                    evt.target.parentElement.parentElement.removeChild(evt.target.parentElement);
                    if (inputFileList.length == 0) {
                        document.querySelector('#mult-inputs-message').style.display = 'none';
                        document.querySelector('#clear_inputfilelist_button').style.display = 'none';
                    }
                });
                addEl(sdiv, minus);
                $fileListDiv.append($(sdiv));
                inputFileList.push(file);
            }
        }
    }
    if (inputFileList.length > 0) {
        document.querySelector('#clear_inputfilelist_button').style.display = 'inline-block';
        document.querySelector('#mult-inputs-message').style.display = 'block';
    } else {
        document.querySelector('#clear_inputfilelist_button').style.display = 'none';
        document.querySelector('#mult-inputs-message').style.display = 'none';
    }
    document.querySelector('#input-file').value = '';
}

function addListeners () {
    $('#submit-job-button').click(submit);
    $('#input-text').change(inputChangeHandler);
    $('#input-file').change(inputChangeHandler);
    $('#all-annotators-button').click(allNoAnnotatorsHandler);
    $('#no-annotators-button').click(allNoAnnotatorsHandler);
    $('.input-example-button').click(inputExampleChangeHandler)
    $('#refresh-jobs-table-btn').click(refreshJobsTable);
    $('.threedotsdiv').click(onClickThreeDots);
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
        if (storeModuleDivClicked) {
            var k = evt.key;
            var moduleDiv = document.getElementById('moduledetaildiv_store');
            var moduleListName = moduleDiv.getAttribute('modulelistname');
            var moduleListPos = moduleDiv.getAttribute('modulelistpos');
            var moduleList = moduleLists[moduleListName];
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

function setLastAssembly () {
    let sel = document.getElementById('assembly-select');
    if (!servermode) {
        $.ajax({
            url: '/submit/lastassembly',
            ajax: true,
            success: function (response) {
                sel.value = response;
            },
        });
    } else {
        if (GLOBALS.usersettings.hasOwnProperty('lastAssembly')) {
            sel.value = GLOBALS.usersettings.lastAssembly;
        } else {
            sel.value = null;
        }
    }
}

function getJobById (jobId) {
    return GLOBALS.idToJob[jobId];
}

function updateRunningJobTrs (job) {
    var idx = GLOBALS.jobs.indexOf(job.id);
    if (idx < jobsListCurStart || idx >= jobsListCurEnd) {
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
    inputFileList = [];
}

function populateInputFormats () {
    let inputSel = $('#submit-input-format-select');
    inputSel.prop('disabled',true);
    for (moduleName in localModuleInfo) {
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
    username = urlParams.get('username');
    getServermode();
    connectWebSocket();
    checkConnection();
    populatePackageVersions();
    getBaseModuleNames();
    addListeners();
    resizePage();
    window.onresize = function (evt) {
        resizePage();
    }
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

function populateCaseControl (outer) {
    if ( ! localModuleInfo.hasOwnProperty('casecontrol')) {
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
        .append($(getEl('img')).attr('src','../help.png').attr('id','case-control-help-img'));
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
