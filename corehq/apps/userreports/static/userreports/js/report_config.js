/* global _, $, COMMCAREHQ, django */
var reportBuilder = function () {
    var self = this;

    var PropertyList = hqImport('userreports/js/builder_view_models.js').PropertyList;
    var PropertyListItem = hqImport('userreports/js/builder_view_models.js').PropertyListItem;

    var ColumnProperty = function (getDefaultDisplayText, getPropertyObject, reorderColumns, hasDisplayText) {
        PropertyListItem.call(this, getDefaultDisplayText, getPropertyObject, hasDisplayText);
        this.calculation.subscribe(function () {
            reorderColumns();
        });
    };
    ColumnProperty.prototype = Object.create(PropertyListItem.prototype);
    ColumnProperty.prototype.constructor = ColumnProperty;


    var ColumnList = function(options) {
        PropertyList.call(this, options);
        this.newProperty = ko.observable(null);
        this.suspendReorderColumns = false;
    };
    ColumnList.prototype = Object.create(PropertyList.prototype);
    ColumnList.prototype.constructor = ColumnList;
    ColumnList.prototype._createListItem = function () {
        return new ColumnProperty(
            this.getDefaultDisplayText.bind(this),
            this.getPropertyObject.bind(this),
            this.reorderColumns.bind(this),
            this.hasDisplayCol
        );
    };
    ColumnList.prototype.buttonHandler = function () {
        if (this.newProperty()) {
            var item = this._createListItem();
            item.property(this.newProperty());
            item.calculation(item.getDefaultCalculation());
            this.newProperty(null);
            this.suspendReorderColumns = true;
            this.columns.push(item);
            this.suspendReorderColumns = false;
        }
    };
    ColumnList.prototype.reorderColumns = function () {
        var items = {};

        // In the initialization of this.columns, reorderColumns gets called (because we set the calculation of
        // each ColumnProperty), but we don't want this function to run until the this.columns exists.
        if (this.columns && ! this.suspendReorderColumns) {
            this.columns().forEach(function (v, i) {
                items[[v.property(), v.calculation(), v.displayText()]] = i;
            });

            var isGroupBy = function (column) {
                return column.calculation() === "Group By";
            };
            var index = function (column) {
                return items[[column.property(), column.calculation(), column.displayText()]];
            };
            var compare = function (first, second) {
                // return negative if first is smaller than second
                if (isGroupBy(first) !== isGroupBy(second)) {
                    return isGroupBy(first) ? -1 : 1;
                }
                if (index(first) !== index(second)) {
                    return index(first) < index(second) ? -1 : 1;
                }
                return 0
            };
            this.columns.sort(compare);
        }
    };


    /**
     * ReportConfig is a view model for managing report configuration
     */
    self.ReportConfig = function (config) {
        var self = this;

        self._mapboxAccessToken = config['mapboxAccessToken'];

        self._app = config['app'];
        self._sourceType = config['sourceType'];
        self._sourceId = config['sourceId'];

        self.existingReportId = config['existingReport'];

        self.columnOptions = config["columnOptions"];  // Columns that could be added to the report
        self.reportPreviewUrl = config["reportPreviewUrl"];  // Fetch the preview data asynchronously.

        self.reportTypeListLabel = (config['sourceType'] === "case") ? "Case List" : "Form List";
        self.reportTypeAggLabel = (config['sourceType'] === "case") ? "Case Summary" : "Form Summary";
        self.reportType = ko.observable(config['existingReportType'] || 'list');
        self.reportType.subscribe(function (newValue) {
            self.columnList.suspendReorderColumns = true;
            var wasAggregationEnabled = self.isAggregationEnabled();
            self.isAggregationEnabled(newValue === "table");
            self.previewChart(newValue === "table" && self.selectedChart() !== "none");
            if (self.isAggregationEnabled() && !wasAggregationEnabled) {
                self._suspendPreviewRefresh = true;

                self.columnList.columns().forEach(function(val, index) {
                    if (index === 0) {
                        val.calculation("Group By");
                    } else {
                        if (val.property() === "deviceID") {
                            console.log(val.property());
                            console.log(val.getDefaultCalculation());
                        }
                        val.calculation(val.getDefaultCalculation());
                    }
                });
                self._suspendPreviewRefresh = false;
            }
            self.columnList.suspendReorderColumns = false;
            self.refreshPreview();
            self.saveButton.fire('change');
        });

        self.isAggregationEnabled = ko.observable(self.reportType() === "table");

        self.selectedChart = ko.observable('none');
        self.selectedChart.subscribe(function (newValue) {
            if (newValue === "none") {
                self.previewChart(false);
            } else {
                self.previewChart(true);
                self.refreshPreview();
            }
        });

        self.previewChart = ko.observable(false);

        /**
         * Convert the data source properties passed through the template
         * context into objects with the correct format for the select2 and
         * questionsSelect knockout bindings.
         * @param dataSourceIndicators
         * @private
         */
        var _getSelectableProperties = function (dataSourceIndicators) {
            var utils = hqImport('userreports/js/utils.js');
            if (self._optionsContainQuestions(dataSourceIndicators)) {
                return _.compact(_.map(
                    dataSourceIndicators, utils.convertDataSourcePropertyToQuestionsSelectFormat
                ));
            } else {
                return _.compact(_.map(
                    dataSourceIndicators, utils.convertDataSourcePropertyToSelect2Format
                ));
            }
        };

        var _getSelectableReportColumnOptions = function(reportColumnOptions, dataSourceIndicators) {
            var utils = hqImport('userreports/js/utils.js');
            if (self._optionsContainQuestions(dataSourceIndicators)) {
                return _.compact(_.map(
                    reportColumnOptions, utils.convertReportColumnOptionToQuestionsSelectFormat
                ));
            } else {
                return _.compact(_.map(
                    reportColumnOptions, utils.convertReportColumnOptionToSelect2Format
                ));
            }
        };

        /**
         * Return true if the given data source indicators contain question indicators (as opposed to just meta
         * properties or case properties)
         * @param dataSourceIndicators
         * @private
         */
        self._optionsContainQuestions = function (dataSourceIndicators) {
            return _.any(dataSourceIndicators, function (o) {
                return o.type === 'question';
            });
        };

        self.location_field = ko.observable(config['initialLocation']);
        self.location_field.subscribe(function () {
            self.refreshPreview();
        });

        self.optionsContainQuestions = self._optionsContainQuestions(config['dataSourceProperties']);
        self.selectablePropertyOptions = _getSelectableProperties(config['dataSourceProperties']);
        self.selectableReportColumnOptions = _getSelectableReportColumnOptions(self.columnOptions, config['dataSourceProperties']);

        self.columnList = new ColumnList({
            hasFormatCol: false,
            hasCalculationCol: self.isAggregationEnabled,
            initialCols: config['initialColumns'],
            reportType: self.reportType(),
            propertyOptions: self.columnOptions,
            selectablePropertyOptions: self.selectableReportColumnOptions,
        });
        window.columnList = self.columnList;

        self.columnList.serializedProperties.subscribe(function (newValue) {
            self.refreshPreview(newValue);
            self.saveButton.fire('change');
        });

        self.filterList = new PropertyList({
            hasFormatCol: self._sourceType === "case",
            hasCalculationCol: false,
            initialCols: config['initialUserFilters'],
            buttonText: 'Add User Filter',
            analyticsAction: 'Add User Filter',
            propertyHelpText: django.gettext('Choose the property you would like to add as a filter to this report.'),
            displayHelpText: django.gettext('Web users viewing the report will see this display text instead of the property name. Name your filter something easy for users to understand.'),
            formatHelpText: django.gettext('What type of property is this filter?<br/><br/><strong>Date</strong>: Select this if the property is a date.<br/><strong>Choice</strong>: Select this if the property is text or multiple choice.'),
            reportType: self.reportType(),
            propertyOptions: config['dataSourceProperties'],
            selectablePropertyOptions: self.selectablePropertyOptions,
        });
        self.filterList.serializedProperties.subscribe(function () {
            self.saveButton.fire("change");
        });
        self.defaultFilterList = new PropertyList({
            hasFormatCol: true,
            hasCalculationCol: false,
            hasDisplayCol: false,
            hasFilterValueCol: true,
            initialCols: config['initialDefaultFilters'],
            buttonText: 'Add Default Filter',
            analyticsAction: 'Add Default Filter',
            propertyHelpText: django.gettext('Choose the property you would like to add as a filter to this report.'),
            formatHelpText: django.gettext('What type of property is this filter?<br/><br/><strong>Date</strong>: Select this to filter the property by a date range.<br/><strong>Value</strong>: Select this to filter the property by a single value.'),
            filterValueHelpText: django.gettext('What value or date range must the property be equal to?'),
            reportType: self.reportType(),
            propertyOptions: config['dataSourceProperties'],
            selectablePropertyOptions: self.selectablePropertyOptions,
        });
        self.defaultFilterList.serializedProperties.subscribe(function () {
            self.saveButton.fire("change");
        });
        self.previewError = ko.observable(false);
        self._suspendPreviewRefresh = false;
        self.refreshPreview = function (serializedColumns) {
            if (!self._suspendPreviewRefresh) {
                serializedColumns = typeof serializedColumns !== "undefined" ? serializedColumns : self.columnList.serializedProperties();
                $('#preview').hide();
                if (serializedColumns === "[]") {
                    return;  // Nothing to do.
                }
                $.ajax({
                    url: self.reportPreviewUrl,
                    type: 'post',
                    contentType: 'application/json; charset=utf-8',
                    data: JSON.stringify(Object.assign(
                        self.serialize(),
                        {
                            'app': self._app,
                            'source_type': self._sourceType,
                            'source_id': self._sourceId,
                        }
                    )),
                    dataType: 'json',
                    success: self.renderReportPreview,
                    error: function () {
                        self.previewError(true);
                    },
                });
            }
        };

        // true if a map is being displayed. This is different than reportType === "map", because this is
        // only true if the preview function returned a mapSpec.
        self.displayMapPreview = ko.observable(false);

        self.renderReportPreview = function (data) {
            self.previewError(false);
            self._renderTablePreview(data['table']);
            self._renderChartPreview(data['table']);
            self._renderMapPreview(data['map_config'], data["map_data"]);
        };

        self._renderMapPreview = function (mapSpec, mapData) {
            if (self.reportType() === "map" && mapSpec) {
                self.displayMapPreview(true);
                mapSpec.mapboxAccessToken = self._mapboxAccessToken;
                var render = hqImport('reports_core/js/maps.js').render;
                render(mapSpec, mapData.aaData, $("#map-preview-container"));
            } else {
                self.displayMapPreview(false);
            }
        };

        self._renderChartPreview = function (data) {
            var charts = hqImport('reports_core/js/charts.js');
            if (self.selectedChart() !== "none") {
                if (data) {
                    // data looks like headers, followed by rows of values
                    // aaData needs to be a list of dictionaries
                    var columnNames = _.map(self.columnList.columns(), function (c) { return c.property(); });
                    // ^^^ That's not going to work with multiple "Count Per Choice" values, which expand
                    // TODO: Resolve selectedColumns vs. data[0]
                    var aaData = _.map(
                        data.slice(1), // skip the headers, iterate the rows of values
                        function (row) { return _.object(_.zip(columnNames, row)); }
                    );
                } else {
                    var aaData = [];
                }
                var aggColumns = _.filter(self.columnList.columns(), function (c) {
                    return c.calculation() !== "Group By";
                });
                var groupByNames = _.map(
                    _.filter(self.columnList.columns(), function (c) {
                        return c.calculation() === "Group By";
                    }),
                    function (c) { return c.property(); }
                );
                if (aggColumns.length > 0 && groupByNames.length > 0) {
                    var chartSpecs;
                    if (self.selectedChart() === "bar") {
                        var aggColumnsSpec = _.map(aggColumns, function (c) {
                            return {"display": c.displayText(), "column_id": c.property()};
                        });
                        chartSpecs = [{
                            "type": "multibar",
                            "chart_id": "5221328456932991781",
                            "title": null,  // Using the report title looks dumb in the UI; just leave it out.
                            "y_axis_columns": aggColumnsSpec,
                            "x_axis_column": groupByNames[0],
                            "is_stacked": false,
                            "aggregation_column": null,
                        }];
                    } else {
                        // pie
                        chartSpecs = [{
                            "type": "pie",
                            "chart_id": "-6021326752156782988",
                            "title": null,
                            "value_column": aggColumns[0].property(),
                            "aggregation_column": groupByNames[0],
                        }];
                    }
                    charts.render(chartSpecs, aaData, $('#chart'));
                }
            }
        };

        self._renderTablePreview = function (data) {
            if (self.dataTable) {
                self.dataTable.destroy();
            }
            $('#preview').empty();
            self.dataTable = $('#preview').DataTable({
                "autoWidth": false,
                "ordering": false,
                "paging": false,
                "searching": false,
                "columns": _.map(data[0], function(column) { return {"title": column}; }),
                "data": data.slice(1),
            });
            $('#preview').show();
        };

        self.validate = function () {
            var isValid = true;
            if (!self.filterList.validate()) {
                isValid = false;
                $("#userFilterAccordion").collapse('show');
            }
            if (!self.defaultFilterList.validate()) {
                isValid = false;
                $("#defaultFilterAccordion").collapse('show');
            }
            if (!isValid){
                alert('Invalid report configuration. Please fix the issues and try again.');
            }
            return isValid;
        };

        self.serialize = function () {
            return {
                "existing_report": self.existingReportId,
                "report_title": $('#report-title').val(), // From the inline-edit component
                "report_description": $('#report-description').val(),  // From the inline-edit component
                "report_type": self.reportType(),
                "aggregate": self.isAggregationEnabled(),
                "chart": self.selectedChart(),
                "columns": JSON.parse(self.columnList.serializedProperties()),
                "location": self.location_field(),
                "default_filters": JSON.parse(self.defaultFilterList.serializedProperties()),
                "user_filters": JSON.parse(self.filterList.serializedProperties()),
            };
        };

        var button = COMMCAREHQ.SaveButton;
        if (config['existingReport']) {
            button = COMMCAREHQ.makeSaveButton({
                // The SAVE text is the only thing that distringuishes this from COMMCAREHQ.SaveButton
                SAVE: django.gettext("Update Report"),
                SAVING: django.gettext("Saving..."),
                SAVED: django.gettext("Saved"),
                RETRY: django.gettext("Try Again"),
                ERROR_SAVING: django.gettext("There was an error saving"),
            }, 'btn btn-success');
        }

        self.saveButton = button.init({
            unsavedMessage: "You have unsaved settings.",
            save: function () {
                var isValid = self.validate();
                if (isValid) {
                    self.saveButton.ajax({
                        url: window.location.href,  // POST here; keep URL params
                        type: "POST",
                        data: JSON.stringify(self.serialize()),
                        dataType: 'json',
                        success: function (data) {
                            self.existingReportId = data['report_id'];
                        },
                    });
                }
            },
        });
        self.saveButton.ui.appendTo($("#saveButtonHolder"));

        $("#btnSaveView").click(function () {
            var isValid = self.validate();
            if (isValid) {
                $.ajax({
                    url: window.location.href,
                    type: "POST",
                    data: JSON.stringify(Object.assign(self.serialize(), {'delete_temp_data_source': true})),
                    success: function (data) {
                        // Redirect to the newly-saved report
                        self.saveButton.setState('saved');
                        window.location.href = data['report_url'];
                    },
                    dataType: 'json',
                });
            }
        });

        if (!self.existingReportId) {
            self.saveButton.fire('change');
        }
        self.refreshPreview();
        return self;
    };

    return self;

}();
