var servermode = false;
var logged = false;
var username = null;

var GLOBALS = {
    jobs: [],
    annotators: {},
    reports: {},
    inputExamples: {}
}

function submit () {
    if (servermode && logged == false) {
        alert('Log in before submitting a job.');
        return;
    }
    let fd = new FormData();
    var textInputElem = $('#input-text');
    var textVal = textInputElem.val();
    let inputFile = null;
    if (textVal.length > 0) {
        var textBlob = new Blob([textVal], {type:'text/plain'})
        inputFile = new File([textBlob], 'input');
    } else {
        var fileInputElem = $('#input-file')[0];
        if (fileInputElem.files.length > 0) {
            inputFile = fileInputElem.files[0];
        }
    }
    if (inputFile == null) {
        alert('Choose a input variants file, enter variants, or click an input example button.');
        return;
    }
    fd.append('file', inputFile);
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
    var note = document.getElementById('jobnoteinput').value;
    submitOpts.note = note;
    fd.append('options',JSON.stringify(submitOpts));
    $.ajax({
        url:'submit',
        data: fd,
        type: 'POST',
        processData: false,
        contentType: false,
        success: function (data) {
            addJob(data);
            buildJobsTable();
        }
    })
    $('#submit-job-button').attr('disabled','disabled');
    setTimeout(function(){
            $('#submit-job-button').removeAttr('disabled');
        },
        1500
    );
};

function addJob (jsonObj) {
    var trueDate = new Date(jsonObj.submission_time);
    jsonObj.submission_time = trueDate;
    GLOBALS.jobs.push(jsonObj);
    GLOBALS.jobs.sort((a, b) => {
        return b.submission_time.getTime() - a.submission_time.getTime();
    })

}

function createJobExcelReport (evt) {
    var jobid = evt.target.getAttribute('jobId');
    generateReport(jobid, 'excel', function () {
        populateJobs().then(function () {
            buildJobsTable();
        });
    });
}

function createJobTextReport (evt) {
    var jobid = evt.target.getAttribute('jobId');
    generateReport(jobid, 'text', function () {
        populateJobs().then(function () {
            buildJobsTable();
        });
    });
}

function buildJobsTable () {
    var allJobs = GLOBALS.jobs;
    var reportSelectors = $('.report-type-selector');
    var curSelectedReports = {};
    for (let i=0; i<reportSelectors.length; i++) {
        var selector = $(reportSelectors[i]);
        var jobId = selector.attr('jobId');
        var val = selector.val();
        curSelectedReports[jobId] = val;
    }
    $('.job-table-row').remove();
    var jobsTable = $('#jobs-table tbody');
    for (let i = 0; i < allJobs.length; i++) {
        job = allJobs[i];
        var jobTr = $(getEl('tr'))
            .addClass('job-table-row');
        jobsTable.append(jobTr);
        // Input file
        jobTr.append($(getEl('td')).append(job.orig_input_fname));
        // Job ID
        jobTr.append($(getEl('td')).append(job.id));
        // Status
        jobTr.append($(getEl('td')).append(job.status.status));
        // Note
        jobTr.append($(getEl('td')).append(job.note));
        // Genome assembly
        jobTr.append($(getEl('td')).append(job.assembly));
        // View
        var viewTd = $(getEl('td'))
            .css('text-align', 'center');
        jobTr.append(viewTd);
        var viewLink = $(getEl('a'))
            .attr('href',`/result/index.html?dbpath=${job.db_path}&job_id=${job.id}`)
            .attr('target','_blank')
            .append($(getEl('button')).append('Launch').attr('disabled', !job.viewable))
        viewTd.append(viewLink);
        // Database
        var dbTd = $(getEl('td'));
        dbTd.css('text-align', 'center');
        jobTr.append(dbTd);
        var dbLink = $(getEl('a'))
            .attr('href',`jobs/${job.id}/db`)
            .append($(getEl('button')).append('DB'))
        dbTd.append(dbLink);
        // Excel
        var excelButton = $(getEl('button'))
            .append('Excel')
            .attr('jobId',job.id)
        if (job.reports.includes('excel') == false) {
            excelButton.css('background-color', 'red');
            excelButton.click(createJobExcelReport);
        } else {
            excelButton.click(jobExcelDownloadButtonHandler);
        }
        dbTd.append(excelButton);
        // Text
        var textButton = $(getEl('button'))
            .append('Text')
            .attr('jobId',job.id)
        if (job.reports.includes('text') == false) {
            textButton.css('background-color', 'red');
            textButton.click(createJobTextReport);
        } else {
            textButton.click(jobTextDownloadButtonHandler);
        }
        dbTd.append(textButton);
        // Log
        var logLink = $(getEl('a'))
            .attr('href','jobs/'+job.id+'/log')
            .attr('target','_blank')
            .append($(getEl('button')).append('Log'))
        dbTd.append(logLink);

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
        var deleteTd = $(getEl('td'));
        deleteTd.css('text-align', 'center');
        jobTr.append(deleteTd);
        var deleteBtn = $(getEl('button')).append('X');
        deleteTd.append(deleteBtn);
        deleteBtn.attr('jobId', job.id);
        deleteBtn.click(jobDeleteButtonHandler);
    }
}

function reportSelectorChangeHandler (event) {
    var selector = $(event.target);
    var downloadBtn = selector.siblings('.report-download-button');
    var jobId = selector.attr('jobId');
    var reportType = selector.val();
    let job;
    for (let i=0; i<GLOBALS.jobs.length; i++) {
        if (GLOBALS.jobs[i].id === jobId) {
            job = GLOBALS.jobs[i];
            break;
        }
    }
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
}

function addListeners () {
    $('#submit-job-button').click(submit);
    $('#input-text').change(inputChangeHandler);
    $('#input-file').change(inputChangeHandler);
    $('#all-annotators-button').click(allNoAnnotatorsHandler);
    $('#no-annotators-button').click(allNoAnnotatorsHandler);
    $('.input-example-button').click(inputExampleChangeHandler)
    $('#refresh-jobs-table-btn').click(refreshJobsTable);
    $('.jobsdirinput').change(setJobsDir);
}

function inputExampleChangeHandler (event) {
    var elem = $(event.target);
    var val = elem.val();
    var getExampleText = new Promise((resolve, reject) => {
        var cachedText = GLOBALS.inputExamples[val];
        if (cachedText === undefined) {
            var fname = val+'.txt'
            $.ajax({
                url:'input-examples/'+fname,
                type: 'GET',
                contentType: 'application/json',
                success: function (data) {
                    GLOBALS.inputExamples[val] = data;
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
}

var JOB_IDS = []

function populateJobs () {
    return new Promise((resolve, reject) => {
        $.ajax({
            url:'jobs',
            type: 'GET',
            async: false,
            success: function (allJobs) {
                GLOBALS.jobs = [];
                for (var i=0; i<allJobs.length; i++) {
                    let job = allJobs[i];
                    addJob(job);
                }
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
            checked: true
        })
    }
    buildCheckBoxGroup(checkDatas, annotCheckDiv);
}

function buildCheckBoxGroup (checkDatas, parentDiv) {
    parentDiv = (parentDiv === undefined) ? getEl('div') : parentDiv;
    emptyElement(parentDiv);
    parentDiv.className = 'checkbox-group';
    // all-none buttons
    var allNoneDiv = getEl('div');
    addEl(parentDiv, allNoneDiv);
    allNoneDiv.className = 'checkbox-group-all-none-div';
    var parentId = parentDiv.id;
    if (parentId != 'report-select-div') {
        // all button
        allButton = getEl('button');
        addEl(allNoneDiv, allButton);
        allButton.className = 'checkbox-group-all-button';
        allButton.textContent = 'All';
        allButton.addEventListener('click', function (evt) {checkBoxGroupAllNoneHandler (evt);});
        // none button
        noneButton = getEl('button');
        addEl(allNoneDiv, noneButton);
        noneButton.className = 'checkbox-group-none-button';
        noneButton.textContent = 'None';
        noneButton.addEventListener('click', function (evt) {checkBoxGroupAllNoneHandler (evt);});
    }
    // flexbox
    var flexbox = getEl('div');
    addEl(parentDiv, flexbox);
    //flexbox.addClass('checkbox-group-flexbox');
    var checkDivs = [];
    // checks
    for (let i=0; i<checkDatas.length; i++) {
        var checkData = checkDatas[i];
        var checkDiv = getEl('div');
        addEl(flexbox, checkDiv);
        var check = getEl('input');
        check.className = 'checkbox-group-check';
        check.setAttribute('type', 'checkbox');
        check.setAttribute('name', checkData.name);
        check.setAttribute('value', checkData.value);
        check.setAttribute('checked', checkData.check);
        addEl(checkDiv, check);
        var label = getEl('span');
        label.style.fontFamily = 'monospace';
        label.style.fontSize = '16px';
        label.textContent = checkData.label;
        addEl(checkDiv, label);
        if (parentId != 'report-select-div') {
            var question = getEl('button');
            question.className = 'moduledetailbutton';
            question.textContent = '?';
            question.setAttribute('module', checkData.value);
            question.addEventListener('click', function (evt) {
                var annotchoosediv = document.getElementById('annotchoosediv');
                var moduledetaildiv = document.getElementById('moduledetaildiv_submit');
                if (moduledetaildiv != null) {
                    annotchoosediv.removeChild(moduledetaildiv);
                }
                var detaildiv = getModuleDetailDiv(evt.target.getAttribute('module'));
                addEl(annotchoosediv, detaildiv);
            });
            addEl(checkDiv, question);
        } else {
            checkDiv.style.display = 'inline-block';
        }
        checkDivs.push(checkDiv);
    }
    // resize all to match max
    /*
    var maxWidth = Math.max.apply(null, checkDivs.map(elem => elem.width()));
    for (let i=0; i<checkDivs.length; i++) {
        let checkDiv = checkDivs[i];
        checkDiv.width(maxWidth);
    }
    */
    return parentDiv;
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
        document.getElementById('jobsdirtext').textContent = response;
    });
}

function setJobsDir (evt) {
    var d = evt.target.value;
    $.get('/submit/setjobsdir', {'jobsdir': d}).done(function (response) {
        document.getElementById('jobsdirtext').textContent = response;
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
        s.textContent = response['path'];
        var ta = document.getElementById('sysconftextarea');
        ta.value = response['content'];
    });
}

function updateSystemConf () {
    var data = {'sysconfstr': document.getElementById('sysconftextarea').value};
    $.ajax({
        url:'/submit/updatesystemconf',
        data: data,
        type: 'POST',
        success: function (response) {
            if (response['success'] == true) {
                alert('System configuration has been updated.');
            } else {
                alert('System configuration was not successful');
            }
            if (response['sysconf']['jobs_dir'] != undefined) {
                populateJobs();
                /*
                populateJobs().then(function () {
                    buildJobsTable();
                });
                */
            }
        }
    });
}

function resetSystemConf () {
    $.get('/submit/resetsystemconf').done(function (response) {
        var status = response['status'];
        if (status == 'success') {
            var d = response['dict'];
            document.getElementById('sysconftextarea').value = d;
        } else {
            alert('Resetting system conf file failed.');
        }
    });
}

function showMd () {
    $.get('/store/getmd').done(function (response) {
        document.getElementById('modulesdirspan').textContent = response;
    });
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
}

function setupServerMode () {
    document.getElementById('accountdiv').style.display = 'block';
    document.getElementById('settingsdiv').style.display = 'none';
    document.getElementById('settingspageselect').style.display = 'none';
    checkLogged();
}

function setupAdminMode () {
    document.getElementById('accountdiv').style.display = 'block';
    document.getElementById('settingsdiv').style.display = 'block';
    document.getElementById('settingspageselect').style.display = 'inline-block';
}

function showLoggedControl (username) {
    var userDiv = document.getElementById('userdiv');
    userDiv.textContent = username;
    userDiv.style.display = 'inline-block';
    document.getElementById('logoutdiv').style.display = 'inline-block';
    document.getElementById('loginsignupbutton').style.display = 'none';
    document.getElementById('settingspageselect').style.display = 'none';
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
                populateJobs();
                var userDiv = document.getElementById('userdiv');
                userDiv.textContent = '';
                userDiv.style.display = 'none';
                document.getElementById('loginsignupbutton').style.display = 'inline-block';
                document.getElementById('logoutdiv').style.display = 'none';
            }
        }
    });
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
            } else {
                msgAccountDiv(msg);
            }
        }
    });
}

function forgotPassword () {
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
            } else if (response == 'fail') {
                msgAccountDiv('Signup failed');
            }
        }
    });
}

function checkLogged () {
    $.ajax({
        url: '/submit/checklogged',
        success: function (response) {
            logged = response['logged'];
            if (logged == true) {
                username = response['email'];
                logged = true;
                doAfterLogin();
            }
        }
    });
}

function populatePackageVersions () {
    $.get('/submit/packageversions').done(function(data){
        let curver = data.current;
        let latver = data.latest;
        $('#curverspan').text(curver);
        const latverspan = $('#latestverspan')
        latverspan.text(latver);
        if (data.update) {
            latverspan.css('color','red');
        }
	});
}

function websubmit_run () {
    getServermode();
    var md = showMd();
    var storediv = document.getElementById('storediv');
    storediv.style.display = 'none';
    connectWebSocket();
    getBaseModuleNames();
    getRemote();
    getLocal();
    document.addEventListener('click', function (evt) {
        if (evt.target.closest('#moduledetaildiv_submit') == null && evt.target.closest('.moduledetailbutton') == null ) {
            var div = document.getElementById('moduledetaildiv_submit');
            if (div != null) {
                div.style.display = 'none';
            }
        }
    });
    window.addEventListener('resize', function (evt) {
        var moduledetaildiv = document.getElementById('moduledetaildiv_submit');
        if (moduledetaildiv == null) {
            return;
        }
        var tdHeight = (window.innerHeight * 0.8 - 150) + 'px';
        var tds = document.getElementById('moduledetaildiv_submit').getElementsByTagName('table')[1].getElementsByTagName('td');
        tds[0].style.height = tdHeight;
        tds[1].style.height = tdHeight;
    });
    addListeners();
    if (servermode == false) {
        populateJobs();
    }
    populateAnnotators();
    if (servermode == false) {
        populateReports();
    }
    getJobsDir();
    var submitcontentdiv = document.getElementById('submit-form');
    var h = window.innerHeight - 235;
    submitcontentdiv.style.height = h + 'px';
    loadSystemConf();
    populatePackageVersions();
};

