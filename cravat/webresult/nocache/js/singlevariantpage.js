var CLOSURE_NO_DEPS = true;
var annotData = null;
//var widgetContainerDiv = null;
var sectionWidth = 1200;

function getInputDataFromUrl () {
    var urlParams = new URLSearchParams(window.location.search);
    var inputChrom = urlParams.get('chrom');
    var inputPos = urlParams.get('pos');
    var inputRef = urlParams.get('ref_base');
    var inputAlt = urlParams.get('alt_base');
    var inputData = cleanInputData(inputChrom, inputPos, inputRef, inputAlt);
    return inputData;
}

function cleanInputData (inputChrom, inputPos, inputRef, inputAlt) {
    if (inputChrom == '') {
        inputChrom = null;
    }
    if (inputPos == '') {
        inputPos = null;
    }
    if (inputRef == '') {
        inputRef = null;
    }
    if (inputAlt == '') {
        inputAlt = null;
    }
    if (inputChrom == null || inputPos == null || inputRef == null || inputAlt == null) {
        return null;
    } else {
        return {'chrom': inputChrom, 'pos': inputPos, 'ref': inputRef, 'alt': inputAlt};
    }
}

function submitForm () {
    var value = document.querySelector('#input_variant').value;
    var toks = value.split(':');
    if (toks.length != 4) {
        return;
    }
    var chrom = toks[0];
    var pos = toks[1];
    var ref = toks[2];
    var alt = toks[3];
    var inputData = cleanInputData(chrom, pos, ref, alt);
    if (inputData != null) {
        submitAnnotate(inputData['chrom'], inputData['pos'], inputData['ref'], inputData['alt']);
    }
}

function submitAnnotate (inputChrom, inputPos, inputRef, inputAlt) {
    var url = '/submit/annotate';
    var params = {'chrom':inputChrom, 'pos':parseInt(inputPos), 'ref_base':inputRef, 'alt_base':inputAlt};
    $.ajax({
        type: 'POST',
        url: url,
        data: params,
        success: function (response) {
            annotData = response;
            annotData['base'] = annotData['crx'];
            showAnnotation(response);
        }
    });
}

function getModulesData (moduleNames) {
    var data = {};
    for (var i = 0; i < moduleNames.length; i++) {
        var moduleName = moduleNames[i];
        var moduleData = annotData[moduleName];
        if (moduleData == null) {
            continue;
        }
        var moduleDataKeys = Object.keys(moduleData);
        for (var j = 0; j < moduleDataKeys.length; j++) {
            var key = moduleDataKeys[j];
            var value = moduleData[key];
            data[moduleName + '__' + key] = value;
        }
    }
    return data;
}

function showWidget (widgetName, moduleNames, level, parentDiv, maxWidth, maxHeight, showTitle) {
    var generator = widgetGenerators[widgetName];
    var divs = null;
    var maxWidthParent = null;
    var maxHeightParent = null;
    if (maxWidth != undefined || maxWidth != null) {
        generator[level]['width'] = null;
        generator[level]['max-width'] = maxWidth;
        maxWidthParent = maxWidth + 30;
    }
    if (maxHeight != undefined || maxHeight != null) {
        generator[level]['height'] = null;
        generator[level]['max-height'] = maxHeight;
        maxHeightParent = maxHeight + 30;
    }
    if (level != undefined) {
        divs = getDetailWidgetDivs(level, widgetName, widgetInfo[widgetName].title, maxWidthParent, maxHeightParent, showTitle);
    } else {
        if ('variant' in generator) {
            divs = getDetailWidgetDivs('variant', widgetName, widgetInfo[widgetName].title, maxWidthParent, maxHeightParent, showTitle);
            level = 'variant';
        } else if ('gene' in generator) {
            divs = getDetailWidgetDivs('gene', widgetName, widgetInfo[widgetName].title, maxWidthParent, maxHeightParent, showTitle);
            level = 'gene';
        }
    }
    var data = getModulesData(moduleNames);
    if (Object.keys(data).length == 0) {
        var span = getNodataSpan();
        span.style.paddingLeft = '7px';
        addEl(divs[1], span);
        //var ret = widgetGenerators[widgetName][level]['function'](divs[1], data, 'variant', true); // last true is to highlight if value exists.
    } else {
        if (level == 'gene') {
            data['base__hugo'] = annotData['crx'].hugo;
        }
        var ret = widgetGenerators[widgetName][level]['function'](divs[1], data, 'variant', true); // last true is to highlight if value exists.
    }
    addEl(parentDiv, divs[0]);
    return divs;
}

function showAnnotation (response) {
    document.querySelectorAll('.detailcontainerdiv').forEach(function (el) {
        $(el).empty();
    });
    hideSpinner();
    var parentDiv = document.querySelector('#contdiv_vannot');
    parentDiv.style.position = 'relative';
    parentDiv.style.width = sectionWidth + 'px';
    parentDiv.style.height = '460px';
    showWidget('basepanel', ['base', 'lollipop', 'hgvs'], 'variant', parentDiv);
    var parentDiv = document.querySelector('#contdiv_cancer');
    showWidget('cancerpanel', ['base', 'chasmplus', 'civic', 'cosmic', 'cgc', 'cgl', 'target'], 'variant', parentDiv, undefined, undefined, false);
    var parentDiv = document.querySelector('#contdiv_af');
    showWidget('poppanel', ['base', 'gnomad', 'thousandgenomes', 'hgdp', 'esp6500', 'abraom', 'uk10k_cohort'], 'variant', parentDiv);
    var parentDiv = document.querySelector('#contdiv_clinrel');
    showWidget('clinpanel', ['base', 'pharmgkb', 'clinvar', 'clingen', 'denovo', 'gwas_catalog'], 'variant', parentDiv, null, null, false);
    var parentDiv = document.querySelector('#contdiv_gene');
    showWidget('genepanel', ['base', 'ess_gene', 'gnomad_gene', 'prec', 'phi', 'ghis', 'loftool', 'interpro', 'gtex', 'rvis', 'ncbigene'], 'variant', parentDiv, null, null, false);
    var parentDiv = document.querySelector('#contdiv_patho');
    showWidget('pathopanel', ['base', 'vest', 'mutpred1', 'mutation_assessor', 'fathmm', 'phdsnpg'], 'variant', parentDiv, null, null, false);
    var parentDiv = document.querySelector('#contdiv_evol');
    showWidget('evolpanel', ['base', 'phastcons', 'phylop'], 'variant', parentDiv, null, null, false);
    var parentDiv = document.querySelector('#contdiv_noncoding');
    showWidget('noncodingpanel', ['base', 'linsight', 'ncrna', 'pseudogene'], 'variant', parentDiv, null, null, false);
    var parentDiv = document.querySelector('#contdiv_interact');
    showWidget('intpanel', ['base', 'biogrid', 'intact'], 'gene', parentDiv, null, null, false);
    var parentDiv = document.querySelector('#contdiv_visu');
    showWidget('visupanel', ['base', 'ndex', 'mupit'], 'variant', parentDiv, null, 'unset', false);
}

function getWidgets (callback, callbackArgs) {
    $.get('/result/service/widgetlist', {}).done(function (jsonResponseData) {
        var tmpWidgets = jsonResponseData;
        var widgetLoadCount = 0;
        for (var i = 0; i < tmpWidgets.length; i++) {
            var tmpWidget = tmpWidgets[i];
            var widgetName = tmpWidget['name'];
            var widgetNameNoWg = widgetName.substring(2);
            widgetInfo[widgetNameNoWg] = tmpWidget;
            $.getScript('/result/widgetfile/' + widgetName + '/' + widgetName + '.js', function () {
                widgetLoadCount += 1;
                if (widgetLoadCount == tmpWidgets.length) {
                    callback(callbackArgs);
                }
            });
        }
    });
}

function getNodataSpan () {
    var span = getEl('span');
    span.classList.add('nodata');
    span.textContent = 'No annotation available';
    return span;
}

var widgetInfo = {};
var widgetGenerators = {};

widgetInfo['basepanel'] = {'title': ''};
widgetGenerators['basepanel'] = {
    'variant': {
        'width': sectionWidth,
        'height': undefined,
        'function': function (div, row, tabName) {
            var generator = widgetGenerators['base']['variant'];
            generator['width'] = 450;
            var divs = showWidget('base', ['base', 'dbsnp'], 'variant', div, null, 220);
            divs[0].style.position = 'absolute';
            divs[0].style.top = '0px';
            divs[0].style.left = '0px';
            var generator = widgetGenerators['hgvs']['variant'];
            generator['width'] = 400;
            var divs = showWidget('hgvs', ['base', 'hgvs'], 'variant', div, null, 220);
            divs[0].style.position = 'absolute';
            divs[0].style.top = '0px';
            divs[0].style.left = '470px';
            var generator = widgetGenerators['lollipop']['variant'];
            generator['width'] = sectionWidth;
            generator['height'] = 200;
            generator['variables']['hugo'] = '';
            annotData['base']['numsample'] = 1;
            var divs = showWidget('lollipop', ['base'], 'variant', div);
            divs[0].style.position = 'absolute';
            divs[0].style.top = '250px';
            divs[0].style.left = '0px';
        }
    }
}

widgetInfo['poppanel'] = {'title': ''};
widgetGenerators['poppanel'] = {
    'variant': {
        'width': '100%',
        'height': undefined,
        'function': function (div, row, tabName) {
            var table = getEl('table');
            var tr = getEl('tr');
            var td = getEl('th');
            td.style.width = '100px';
            td.textContent = 'gnomAD';
            addEl(tr, td);
            var td = getEl('td');
            addBarComponent(td, row, 'Total', 'gnomad__af', tabName);
            addBarComponent(td, row, 'African', 'gnomad__af_afr', tabName);
            addBarComponent(td, row, 'American', 'gnomad__af_amr', tabName);
            addBarComponent(td, row, 'Ashkenazi', 'gnomad__af_asj', tabName);
            addBarComponent(td, row, 'East Asn', 'gnomad__af_eas', tabName);
            addBarComponent(td, row, 'Finn', 'gnomad__af_fin', tabName);
            addBarComponent(td, row, 'Non-Finn Eur', 'gnomad__af_nfe', tabName);
            addBarComponent(td, row, 'Other', 'gnomad__af_oth', tabName);
            addBarComponent(td, row, 'South Asn', 'gnomad__af_sas', tabName);
            addEl(tr, td);
            addEl(table, tr);
            var tr = getEl('tr');
            var td = getEl('th');
            td.textContent = '1000 Genomes';
            addEl(tr, td);
            var td = getEl('td');
            addBarComponent(td, row, 'Total', 'thousandgenomes__af', tabName);
            addBarComponent(td, row, 'African', 'thousandgenomes__afr_af', tabName);
            addBarComponent(td, row, 'American', 'thousandgenomes__amr_af', tabName);
            addBarComponent(td, row, 'East Asn', 'thousandgenomes__eas_af', tabName);
            addBarComponent(td, row, 'European', 'thousandgenomes__eur_af', tabName);
            addBarComponent(td, row, 'South Asn', 'thousandgenomes__sas_af', tabName);
            addEl(table, addEl(tr, td));
            var tr = getEl('tr');
            var td = getEl('th');
            td.textContent = 'HGDP';
            addEl(tr, td);
            var td = getEl('td');
            addBarComponent(td, row, 'European', 'hgdp__european_allele_freq', tabName);
            addBarComponent(td, row, 'African', 'hgdp__african_allele_freq', tabName);
            addBarComponent(td, row, 'Mid. Eastern', 'hgdp__middle_eastern_allele_freq', tabName);
            addBarComponent(td, row, 'East Asn', 'hgdp__east_asian_allele_freq', tabName);
            addBarComponent(td, row, 'CS Asn', 'hgdp__cs_asian_allele_freq', tabName);
            addBarComponent(td, row, 'Oceanian', 'hgdp__oceanian_allele_freq', tabName);
            addBarComponent(td, row, 'Native Amr', 'hgdp__native_american_allele_freq', tabName);
            addEl(table, addEl(tr, td));
            var tr = getEl('tr');
            var td = getEl('th');
            td.textContent = 'ESP6500';
            addEl(tr, td);
            var td = getEl('td');
            addBarComponent(td, row, 'Eur. Amr.', 'esp6500__ea_pop_af', tabName);
            addBarComponent(td, row, 'Afr. Amr.', 'esp6500__aa_pop_af', tabName);
            addEl(table, addEl(tr, td));
            var tr = getEl('tr');
            var td = getEl('th');
            td.textContent = 'ABRaOM';
            addEl(tr, td);
            var td = getEl('td');
            addBarComponent(td, row, 'Allele Freq.', 'abraom__allele_freq', tabName);
            addEl(table, addEl(tr, td));
            var tr = getEl('tr');
            var td = getEl('th');
            td.textContent = 'UK10k Cohorts';
            addEl(tr, td);
            var td = getEl('td');
            addInfoLine(td, 'Twins Alternative Allele Count', getWidgetData(tabName, 'uk10k_cohort', row, 'uk10k_twins_ac'), tabName);
            addBarComponent(td, row, 'Twins Alternative Allele Frequency', 'uk10k_cohort__uk10k_twins_af', tabName);
            addInfoLine(td, 'ALSPAC Alternative Allele Count', getWidgetData(tabName, 'uk10k_cohort', row, 'uk10k_alspac_ac'), tabName);
            addBarComponent(td, row, 'ALSPAC Alternative Allele Frequency', 'uk10k_cohort__uk10k_alspac_af', tabName);
            addEl(table, addEl(tr, td));
            addEl(div, table);
        }
    }
}

widgetInfo['cancerpanel'] = {'title': ''};
widgetGenerators['cancerpanel'] = {
    'variant': {
        'width': sectionWidth,
        'height': null,
        'function': function (div, row, tabName) {
            var table2 = getEl('table');
            table2.style.borderCollapse = 'collapse';
            table2.style.width = '100%';
            var tr2 = getEl('tr');
            tr2.style.borderBottom = '1px dotted #cccccc';
            var td2 = getEl('th');
            td2.style.width = '160px';
            td2.textContent = 'CHASMplus';
            addEl(tr2, td2);
            var td2 = getEl('td');
            var generator = widgetGenerators['chasmplus']['variant'];
            generator.height = null;
            var score = getWidgetData(tabName, 'chasmplus', row, 'score');
            if (score == undefined) {
                var span = getNodataSpan();
                span.style.paddingLeft = '7px';
                addEl(td2, span);
            } else {
                showWidget('chasmplus', ['chasmplus'], 'variant', td2, undefined, 'unset', false);
            }
            addEl(tr2, td2);
            addEl(table2, tr2);
            var tr2 = getEl('tr');
            tr2.style.borderBottom = '1px dotted #cccccc';
            var td2 = getEl('th');
            td2.textContent = 'CiVIC';
            addEl(tr2, td2);
            var td2 = getEl('td');
            td2.style.paddingLeft = '7px';
            var value = getWidgetData(tabName, 'civic', row, 'clinical_a_score');
            if (value == undefined || value == '') {
                var span = getNodataSpan();
                addEl(td2, span);
            } else {
                addInfoLine(td2, 'Clinical actionability score', getWidgetData(tabName, 'civic', row, 'clinical_a_score'), tabName);
                addInfoLine(td2, 'Description', getWidgetData(tabName, 'civic', row, 'description'), tabName);
                addInfoLine(td2, 'Diseases', getWidgetData(tabName, 'civic', row, 'diseases'), tabName);
            }
            addEl(tr2, td2);
            addEl(table2, tr2);
            var tr2 = getEl('tr');
            tr2.style.borderBottom = '1px dotted #cccccc';
            //tr2.style.height = '150px';
            var td2 = getEl('th');
            td2.textContent = 'COSMIC';
            addEl(tr2, td2);
            var td2 = getEl('td');
            var value = getWidgetData(tabName, 'cosmic', row, 'cosmic_id');
            if (value == undefined || value == '') {
                var span = getNodataSpan();
                span.style.paddingLeft = '7px';
                addEl(td2, span);
            } else {
                showWidget('cosmic', ['cosmic'], 'variant', td2, null, 'unset', false);
            }
            addEl(tr2, td2);
            addEl(table2, tr2);
            var tr2 = getEl('tr');
            tr2.style.borderBottom = '1px dotted #cccccc';
            var td2 = getEl('th');
            td2.textContent = 'Cancer Gene Census';
            addEl(tr2, td2);
            var td2 = getEl('td');
            td2.style.paddingLeft = '7px';
            var cls = getWidgetData(tabName, 'cgc', row, 'class');
            var inheritance = getWidgetData(tabName, 'cgc', row, 'inheritance');
            var stype = getWidgetData(tabName, 'cgc', row, 'tts');
            var gtype = getWidgetData(tabName, 'cgc', row, 'ttg');
            if (cls != undefined) {
                if (cls == 'TSG') {
                    cls = 'tumor suppressor gene';
                }
                var span = getEl('div');
                span.textContent = cls + ' with inheritance ' + inheritance + '.';
                addEl(td2, span);
                var span = getEl('div');
                span.textContent = 'Somatic types are ' + stype + '.';
                addEl(td2, span);
                var span = getEl('div');
                span.textContent = 'Germline types are ' + gtype + '.';
                addEl(td2, span);
            } else {
                var span = getNodataSpan();
                addEl(td2, span);
            }
            addEl(tr2, td2);
            addEl(table2, tr2);
            var tr2 = getEl('tr');
            tr2.style.borderBottom = '1px dotted #cccccc';
            var td2 = getEl('th');
            td2.style.paddingLeft = '7px';
            td2.textContent = 'Cancer Genome Landscape';
            addEl(tr2, td2);
            var td2 = getEl('td');
            td2.style.paddingLeft = '7px';
            var cls = getWidgetData(tabName, 'cgl', row, 'class');
            if (cls != undefined) {
                if (cls == 'TSG') {
                    cls = 'tumor suppressor gene';
                }
                var span = getEl('div');
                span.textContent = 'identified as ' + cls + '.';
                addEl(td2, span);
            } else {
                var span = getNodataSpan();
                addEl(td2, span);
            }
            addEl(tr2, td2);
            addEl(table2, tr2);
            var tr2 = getEl('tr');
            tr2.style.borderBottom = '1px dotted #cccccc';
            var td2 = getEl('th');
            td2.textContent = 'TARGET';
            addEl(tr2, td2);
            var td2 = getEl('td');
            td2.style.paddingLeft = '7px';
            var therapy = getWidgetData(tabName, 'target', row, 'therapy');
            var rationale = getWidgetData(tabName, 'target', row, 'rationale');
            if (therapy != undefined) {
                var span = getEl('div');
                span.textContent = 'identifies this gene is associated with therapy ' + therapy + '. The rationale is ' + rationale;
                addEl(td2, span);
            } else {
                var span = getNodataSpan();
                addEl(td2, span);
            }
            addEl(tr2, td2);
            addEl(table2, tr2);
            addEl(div, table2);
        }
    }
}

widgetInfo['clinpanel'] = {'title': ''};
widgetGenerators['clinpanel'] = {
    'variant': {
        'width': sectionWidth,
        'height': 'unset',
        'function': function (div, row, tabName) {
            var table = getEl('table');
            table.style.borderCollapse = 'collapse';
            table.style.width = '100%';
            var tr = getEl('tr');
            tr.style.borderBottom = '1px dotted #cccccc';
            var td = getEl('th');
            td.style.width = '120px';
            td.textContent = 'PharmGKB';
            addEl(tr, td);
            var td = getEl('td');
            var generator = widgetGenerators['pharmgkb']['variant'];
            generator['width'] = '100%';
            generator['height'] = 'unset';
            if (row['pharmgkb__chemical'] == null) {
                var span = getNodataSpan();
                span.style.paddingLeft = '7px';
                addEl(td, span);
            } else {
                showWidget('pharmgkb', ['pharmgkb'], 'variant', td, null, 'unset', false);
            }
            addEl(tr, td);
            addEl(table, tr);
            var tr = getEl('tr');
            var td = getEl('th');
            tr.style.borderBottom = '1px dotted #cccccc';
            td.textContent = 'ClinVar';
            addEl(tr, td);
            var td = getEl('td');
            if (row['clinvar__id'] == undefined) {
                var span = getNodataSpan();
                span.style.paddingLeft = '7px';
                addEl(td, span);
            } else {
                showWidget('clinvar', ['clinvar'], 'variant', td, null, 'unset', false);
            }
            addEl(tr, td);
            addEl(table, tr);
            var tr = getEl('tr');
            tr.style.borderBottom = '1px dotted #cccccc';
            var td = getEl('th');
            td.textContent = 'ClinGen';
            addEl(tr, td);
            var td = getEl('td');
            if (row['clingen__disease'] == undefined) {
                var span = getNodataSpan();
                span.style.paddingLeft = '7px';
                addEl(td, span);
            } else {
                showWidget('clingen', ['clingen'], 'gene', td, null, 'unset', false);
            }
            addEl(tr, td);
            addEl(table, tr);
            var tr = getEl('tr');
            tr.style.borderBottom = '1px dotted #cccccc';
            var td = getEl('th');
            td.textContent = 'denovo-db';
            addEl(tr, td);
            var td = getEl('td');
            if (row['denovo__PubmedId'] == undefined) {
                var span = getNodataSpan();
                span.style.paddingLeft = '7px';
                addEl(td, span);
            } else {
                showWidget('denovo', ['denovo'], 'variant', td, null, 'unset', false);
            }
            addEl(tr, td);
            addEl(table, tr);
            var tr = getEl('tr');
            tr.style.borderBottom = '1px dotted #cccccc';
            var td = getEl('th');
            td.textContent = 'GWAS Catalog';
            addEl(tr, td);
            var td = getEl('td');
            if (row['gwas_catalog__risk_allele'] == undefined) {
                var span = getNodataSpan();
                span.style.paddingLeft = '7px';
                addEl(td, span);
            } else {
                showWidget('gwas_catalog', ['gwas_catalog'], 'variant', td, null, 'unset', false);
            }
            addEl(tr, td);
            addEl(table, tr);
            addEl(div, table);
        }
    }
}

widgetInfo['genepanel'] = {'title': ''};
widgetGenerators['genepanel'] = {
    'variant': {
        'width': '100%',
        'height': 'unset',
        'function': function (div, row, tabName) {
            var table = getEl('table');
            var tr = getEl('tr');
            var td = getEl('td');
			var value = getWidgetData(tabName, 'ess_gene', row, 'ess_gene');
            if (value != undefined) {
                if (value == 'E') {
                    value = 'essential';
                } else if (value == 'N') {
                    value = 'non-essential';
                }
                var span = getEl('div');
                span.textContent = 'This gene is ' + value + ' determined by evolutionary genomics analysis of human orthologs of essential genes.';
                addEl(td, span);
                addEl(tr, td);
                addEl(table, tr);
                var tr = getEl('tr');
                var td = getEl('td');
            }
            td.style.position = 'relative';
            showWidget('gnomad_gene', ['gnomad_gene'], 'gene', td, null, 280);
            addEl(tr, td);
            addEl(table, tr);
            var tr = getEl('tr');
            addEl(table, tr);
            var td = getEl('td');
            td.style.position = 'relative';
            addEl(tr, td);
            var table2 = getEl('table');
            var tr2 = getEl('tr');
            var td2 = getEl('td');
            addEl(tr2, td2);
            showWidget('prec', ['prec'], 'gene', td2);
            td2 = getEl('td');
            td2.style.position = 'relative';
            addEl(tr2, td2);
            showWidget('phi', ['phi'], 'gene', td2);
            td2 = getEl('td');
            td2.style.position = 'relative';
            addEl(tr2, td2);
            showWidget('ghis', ['ghis'], 'gene', td2);
            td2 = getEl('td');
            td2.style.position = 'relative';
            addEl(tr2, td2);
            showWidget('loftool', ['loftool'], 'gene', td2);
            addEl(table2, tr2);
            addEl(td, table2);
            var tr = getEl('tr');
            var td = getEl('td');
            var table2 = getEl('table');
            var tr2 = getEl('tr');
            var td2 = getEl('td');
            showWidget('interpro', ['interpro'], 'variant', td2);
            addEl(tr2, td2);
            var td2 = getEl('td');
            showWidget('gtex', ['gtex'], 'variant', td2);
            addEl(table2, addEl(tr2, td2));
            addEl(td, table2);
            addEl(tr, td);
            var tr = getEl('tr');
            var td = getEl('td');
            showWidget('rvis', ['rvis'], 'gene', td);
            addEl(table, addEl(tr, td));
            var tr = getEl('tr');
            var td = getEl('td');
            showWidget('ncbigene', ['ncbigene'], 'gene', td, 1175, 300);
            addEl(table, addEl(tr, td));
            addEl(div, table);
        }
    }
}

widgetInfo['pathopanel'] = {'title': ''};
widgetGenerators['pathopanel'] = {
    'variant': {
        'width': '100%',
        'max-height': 'unset',
        'function': function (div, row, tabName) {
            var table = getEl('table');
            var tr = getEl('tr');
            var td = getEl('td');
            var table2 = getEl('table');
            var tr2 = getEl('tr');
            var td2 = getEl('td');
            showWidget('vest', ['vest'], 'variant', td2, undefined, 'unset', true);
            addEl(tr2, td2);
            var td2 = getEl('td');
            showWidget('phdsnpg', ['phdsnpg'], 'variant', td2, undefined, 'unset', true);
            addEl(tr2, td2);
            var td2 = getEl('td');
            showWidget('mutpred1', ['mutpred1'], 'variant', td2, undefined, 'unset', true);
            addEl(tr2, td2);
            addEl(table2, tr2);
            addEl(td, table2);
            addEl(tr, td);
            addEl(table, tr);
            var table2 = getEl('table');
            var tr2 = getEl('tr');
            var td2 = getEl('td');
            showWidget('mutation_assessor', ['mutation_assessor'], 'variant', td2, undefined, 'unset', true);
            addEl(tr2, td2);
            var td2 = getEl('td');
            showWidget('fathmm', ['fathmm'], 'variant', td2, undefined, 'unset', true);
            addEl(tr2, td2);
            addEl(table2, tr2);
            addEl(td, table2);
            addEl(tr, td);
            addEl(table, tr);
            addEl(div, table);
        }
    }
}

widgetInfo['evolpanel'] = {'title': ''};
widgetGenerators['evolpanel'] = {
    'variant': {
        'width': sectionWidth,
        'max-height': 'unset',
        'function': function (div, row, tabName) {
            var table = getEl('table');
            table.style.borderCollapse = 'collapse';
            table.style.width = '100%';
            var tr = getEl('tr');
            tr.style.borderBottom = '1px dotted #cccccc';
            var td = getEl('th');
            td.style.width = '100px';
            td.textContent = 'PhastCons';
            addEl(tr, td);
            var td = getEl('td');
            if (row['phastcons__phastcons100_vert'] == undefined) {
                var span = getNodataSpan();
                span.style.paddingLeft = '7px';
                addEl(td, span);
            } else {
                showWidget('phastcons', ['phastcons'], 'variant', td, undefined, 'unset', false);
            }
            addEl(tr, td);
            addEl(table, tr);
            var tr = getEl('tr');
            tr.style.borderBottom = '1px dotted #cccccc';
            var td = getEl('th');
            td.textContent = 'PhyloP';
            addEl(tr, td);
            var td = getEl('td');
            if (row['phylop__phylop100_vert'] == undefined) {
                var span = getNodataSpan();
                span.style.paddingLeft = '7px';
                addEl(td, span);
            } else {
                showWidget('phylop', ['phylop'], 'variant', td, undefined, 'unset', false);
            }
            addEl(tr, td);
            addEl(table, tr);
            addEl(div, table);
        }
    }
}

widgetInfo['noncodingpanel'] = {'title': ''};
widgetGenerators['noncodingpanel'] = {
    'variant': {
        'width': '100%',
        'max-height': 'unset',
        'function': function (div, row, tabName) {
            var table = getEl('table');
            table.style.borderCollapse = 'collapse';
            table.style.width = '100%';
            var tr = getEl('tr');
            tr.style.borderBottom = '1px dotted #cccccc';
            var td = getEl('th');
            td.style.width = '100px';
            td.textContent = 'LINSIGHT';
            addEl(tr, td);
            var td = getEl('td');
            if (row['linsight__value'] == undefined) {
                var span = getNodataSpan();
                span.style.paddingLeft = '7px';
                addEl(td, span);
            } else {
                showWidget('linsight', ['linsight'], 'variant', td, undefined, 'unset', false);
            }
            addEl(tr, td);
            addEl(table, tr);
            var tr = getEl('tr');
            tr.style.borderBottom = '1px dotted #cccccc';
            var td = getEl('th');
            td.textContent = 'ncRNA';
            addEl(tr, td);
            var td = getEl('td');
            if (row['ncrna__ncrnaclass'] == undefined) {
                var span = getNodataSpan();
                span.style.paddingLeft = '7px';
                addEl(td, span);
            } else {
                showWidget('ncrna', ['ncrna'], 'variant', td, undefined, 'unset', false);
            }
            addEl(tr, td);
            addEl(table, tr);
            var tr = getEl('tr');
            tr.style.borderBottom = '1px dotted #cccccc';
            var td = getEl('th');
            td.textContent = 'Pseudogene';
            addEl(tr, td);
            var td = getEl('td');
            if (row['pseudogene__pseudogene_hugo'] == undefined) {
                var span = getNodataSpan();
                span.style.paddingLeft = '7px';
                addEl(td, span);
            } else {
                showWidget('pseudogene', ['pseudogene'], 'variant', td, undefined, 'unset', false);
            }
            addEl(tr, td);
            addEl(table, tr);
            addEl(div, table);
        }
    }
}

widgetInfo['intpanel'] = {'title': ''};
widgetGenerators['intpanel'] = {
    'gene': {
        'width': '100%',
        'max-height': 'unset',
        'function': function (div, row, tabName) {
            var table = getEl('table');
            table.style.width = '100%';
            var tr = getEl('tr');
            var td = getEl('td');
            showWidget('biogrid', ['biogrid'], 'gene', td, null, 300);
            addEl(tr, td);
            var td = getEl('td');
            showWidget('intact', ['intact'], 'gene', td, null, 300);
            addEl(tr, td);
            addEl(table, tr);
            addEl(div, table);
        }
    }
}

widgetInfo['visupanel'] = {'title': ''};
widgetGenerators['visupanel'] = {
    'variant': {
        'width': sectionWidth,
        'height': 'unset',
        'function': function (div, row, tabName) {
            div.style.overflow = 'unset';
            var table = getEl('table');
            var tr = getEl('tr');
            var td = getEl('td');
            td.style.width = sectionWidth + 'px';
            var generator = widgetGenerators['ndex']['gene'];
            var setHeight = null;
            if (row['ndex__networkid'] != undefined) {
                td.style.height = '605px';
                setHeight = 560;
            } else {
                setHeight = 50;
            }
            generator['height'] = setHeight;
            generator['width'] = sectionWidth - 7;
            showWidget('ndex', ['ndex'], 'gene', td, null, height);
            addEl(tr, td);
            addEl(table, tr);
            var tr = getEl('tr');
            var td = getEl('td');
            td.style.width = sectionWidth + 'px';
            var generator = widgetGenerators['mupit2']['variant'];
            generator['width'] = sectionWidth;
            var height = null;
            if (row['mupit__link'] != undefined) {
                td.style.height = '605px';
                height = 560;
            } else {
                height = 50;
            }
            generator['height'] = height;
            generator['width'] = sectionWidth - 7;
            showWidget('mupit2', ['base', 'mupit'], 'variant', td);
            addEl(tr, td);
            addEl(table, tr);
            addEl(div, table);
        }
    }
}

widgetInfo['mupit2'] = {'title': 'MuPIT'};
widgetGenerators['mupit2'] = {
	'variant': {
		'width': 600, 
		'height': 500, 
		'function': function (div, row, tabName) {
            var chrom = getWidgetData(tabName, 'base', row, 'chrom');
            var pos = getWidgetData(tabName, 'base', row, 'pos');
            var url = location.protocol + '//www.cravat.us/MuPIT_Interactive/rest/showstructure/check?pos=' + chrom + ':' + pos;
            var iframe = getEl('iframe');
            iframe.style.position = 'absolute';
            iframe.style.top = '15px';
            iframe.style.left = '0px';
            iframe.style.width = '100%';
            iframe.style.height = '500px';
            iframe.style.border = '0px';
            addEl(div, iframe);
            $.get(url).done(function (response) {
                if (response.hit == true) {
                    iframe.src = location.protocol + '//www.cravat.us/MuPIT_Interactive?gm=' + chrom + ':' + pos + '&embed=true';
                } else {
                    iframe.parentElement.removeChild(iframe);
                    var sdiv = getEl('div');
                    sdiv.textContent = 'No annotation available';
                    sdiv.style.paddingLeft = '7px';
                    sdiv.style.color = '#cccccc';
                    addEl(div, sdiv);
                    div.parentElement.style.height = '50px';
                }
            });
		}
	}
}
function writeToVariantArea (inputData) {
    var value = inputData['chrom'] + ':' + inputData['pos'] + ':' + inputData['ref'] + ':' + inputData['alt'];
    document.querySelector('#input_variant').value = value;
}

function hideSpinner () {
    document.querySelector('#spinnerdiv').style.display = 'none';
}

function showSpinner () {
    document.querySelector('#spinnerdiv').style.display = 'block';
}

function processUrl () {
    var inputData = getInputDataFromUrl();
    if (inputData != null) {
        writeToVariantArea(inputData);
        submitAnnotate(inputData['chrom'], inputData['pos'], inputData['ref'], inputData['alt']);
    }
}

function setupEvents () {
    document.querySelector('#input_variant').addEventListener('keyup', function (evt) {
        evt.stopPropagation();
        if (evt.keyCode == 13) {
            document.querySelector('#input_submit').click();
            //submitForm();
        }
    });
}

function showSearch () {
    document.querySelector('#inputdiv').style.display = 'block';
}

function hideSearch () {
    document.querySelector('#inputdiv').style.display = 'none';
}

function toggleSearch () {
    var display = document.querySelector('#inputdiv').style.display;
    if (display == 'none') {
        showSearch();
    } else if (display == 'block') {
        hideSearch();
    }
}

function onClickSearch () {
    toggleSearch();
}

function run () {
    showSpinner();
    setupEvents();
    getWidgets(processUrl, null);
}

window.onload = function () {
    run();
}

