
document.addEventListener("DOMContentLoaded", function () {
    const calendarEl = document.getElementById("calendar");
    const statusEventsDialog = document.getElementById("statusEventsDialog");
    const statusEventsHeading = document.getElementById("statusEventsHeading");
    const statusEventList = document.getElementById("statusEventList");
    const saveSuccessMessage = document.getElementById("saveSuccessMessage");
    const dialog = document.getElementById("eventDialog");
    const form = document.getElementById("eventForm");
    const formHeading = document.getElementById("eventFormHeading");

    const selectedDateText = document.getElementById("selectedDate");
    const titleInput = document.getElementById("eventTitle");
    const departmentInput = document.getElementById("eventDepartment");
    const venueInput = document.getElementById("eventVenue");
    const startDateInput = document.getElementById("eventStartDate");
    const startDateLabel = document.getElementById("eventStartDateLabel");
    const startInput = document.getElementById("eventStart");
    const endDateInput = document.getElementById("eventEndDate");
    const endDateLabel = document.getElementById("eventEndDateLabel");
    const endInput = document.getElementById("eventEnd");
    const statusInput = document.getElementById("eventStatus");
    const statusLabel = document.getElementById("eventStatusLabel");
    const rescheduleFields = document.getElementById("rescheduleFields");
    const rescheduleStartDateInput = document.getElementById("rescheduleStartDate");
    const rescheduleStartTimeInput = document.getElementById("rescheduleStartTime");
    const rescheduleEndDateInput = document.getElementById("rescheduleEndDate");
    const rescheduleEndTimeInput = document.getElementById("rescheduleEndTime");
    const rescheduleReasonInput = document.getElementById("rescheduleReason");
    const errorText = document.getElementById("formError");
    const saveButton = document.getElementById("saveEventBtn");

    const STATUS_ORDER = ["pending", "approved", "rescheduled", "canceled"];
    const STATUS_LABELS = {
        pending: "Pending",
        approved: "Approved",
        rescheduled: "Rescheduled",
        canceled: "Canceled",
    };
    const STATUS_TRANSITIONS = {
        pending: ["pending", "approved", "canceled"],
        approved: ["approved", "rescheduled", "canceled"],
        rescheduled: ["rescheduled", "approved", "canceled"],
        canceled: ["canceled"],
    };

    let selectedDate = "";
    let cachedEvents = [];
    let eventsLoaded = false;
    let editingEventId = null;
    let originalEditSnapshot = null;
    let autoRescheduleStatus = false;
    let listContext = null;
    let calendar;

    function pad(value) {
        return String(value).padStart(2, "0");
    }

    function toLocalDate(date) {
        return (
            date.getFullYear() +
            "-" +
            pad(date.getMonth() + 1) +
            "-" +
            pad(date.getDate())
        );
    }

    function toLocalTime(date) {
        return pad(date.getHours()) + ":" + pad(date.getMinutes());
    }

    function formatDisplayDate(date) {
        return date.toLocaleDateString(undefined, {
            weekday: "short",
            year: "numeric",
            month: "short",
            day: "numeric",
        });
    }

    function formatDisplayTime(date) {
        return date.toLocaleTimeString(undefined, {
            hour: "numeric",
            minute: "2-digit",
        });
    }

    function venueLabel(value) {
        const option = venueInput.querySelector('option[value="' + value + '"]');
        return option ? option.textContent : value;
    }

    function csrfToken() {
        return form.querySelector('[name="csrfmiddlewaretoken"]').value;
    }

    function eventStatus(event) {
        return event.status || "pending";
    }

    function eventOccupiesDate(event, dateStr) {
        const start = new Date(event.start);
        const end = new Date(event.end);
        const dayStart = new Date(dateStr + "T00:00:00");
        const dayEnd = new Date(dayStart);
        dayEnd.setDate(dayEnd.getDate() + 1);
        return start < dayEnd && end > dayStart;
    }

    function countsForDate(dateStr) {
        const seen = {
            pending: new Set(),
            approved: new Set(),
            rescheduled: new Set(),
            canceled: new Set(),
        };

        cachedEvents.forEach(function (event) {
            if (!eventOccupiesDate(event, dateStr)) {
                return;
            }
            const status = eventStatus(event);
            if (seen[status]) {
                seen[status].add(String(event.id));
            }
        });

        return STATUS_ORDER.map(function (status) {
            return { status: status, count: seen[status].size };
        }).filter(function (item) {
            return item.count > 0;
        });
    }

    function eventsForDateAndStatus(dateStr, status) {
        const seen = new Set();
        return cachedEvents.filter(function (event) {
            if (eventStatus(event) !== status || !eventOccupiesDate(event, dateStr)) {
                return false;
            }
            const id = String(event.id);
            if (seen.has(id)) {
                return false;
            }
            seen.add(id);
            return true;
        }).sort(function (a, b) {
            return new Date(a.start) - new Date(b.start);
        });
    }

    function decorateEvent(event) {
        const status = eventStatus(event);
        return {
            id: event.id,
            title: event.title,
            start: event.start,
            end: event.end,
            classNames: ["event-status-" + status],
            extendedProps: {
                venue: event.venue,
                department: event.department,
                status: status,
            },
        };
    }

    function stopCellClick(event) {
        event.preventDefault();
        event.stopPropagation();
    }

    function cellDateStr(cell, fallbackDate) {
        const attr = cell.getAttribute("data-date");
        if (attr && /^\d{4}-\d{2}-\d{2}$/.test(attr)) {
            return attr;
        }
        return fallbackDate ? toLocalDate(fallbackDate) : "";
    }

    function renderSummariesForCell(cell, dateStr) {
        let container = cell.querySelector(":scope > .day-status-summaries");
        if (!container) {
            container = document.createElement("div");
            container.className = "day-status-summaries";
            const topRow = cell.firstElementChild;
            if (topRow && topRow.nextSibling) {
                cell.insertBefore(container, topRow.nextSibling);
            } else {
                cell.appendChild(container);
            }
        }

        container.replaceChildren();
        countsForDate(dateStr).forEach(function (item) {
            const button = document.createElement("button");
            button.type = "button";
            button.className = "status-" + item.status;
            button.textContent = item.count + " " + STATUS_LABELS[item.status];
            button.addEventListener("click", function (clickEvent) {
                stopCellClick(clickEvent);
                openStatusList(dateStr, item.status);
            });
            ["mousedown", "pointerdown", "mouseup", "touchstart"].forEach(function (type) {
                button.addEventListener(type, stopCellClick);
            });
            container.appendChild(button);
        });
    }

    function renderAllSummaries() {
        const isMonth = currentViewType() === "dayGridMonth";
        calendarEl.querySelectorAll(".day-status-summaries").forEach(function (node) {
            if (!isMonth) {
                node.remove();
            }
        });
        if (!isMonth) {
            return;
        }

        calendarEl.querySelectorAll("[data-date]").forEach(function (cell) {
            const dateStr = cellDateStr(cell);
            if (!dateStr) {
                return;
            }
            renderSummariesForCell(cell, dateStr);
        });
    }

    function currentViewType() {
        return calendar && calendar.view ? calendar.view.type : "dayGridMonth";
    }

    function calendarEvents(events) {
        if (currentViewType() === "dayGridMonth") {
            return [];
        }
        return events.map(decorateEvent);
    }

    function reloadEventsFromServer() {
        return fetch("/api/events/")
            .then(function (response) {
                if (!response.ok) {
                    throw new Error("Unable to load events.");
                }
                return response.json();
            })
            .then(function (events) {
                cachedEvents = events;
                eventsLoaded = true;
                calendar.refetchEvents();
                renderAllSummaries();
                if (listContext && statusEventsDialog.open) {
                    renderStatusList(listContext.dateStr, listContext.status);
                }
                return events;
            });
    }

    function setEditScheduleFieldsVisible(visible) {
        startDateInput.hidden = !visible;
        startDateLabel.hidden = !visible;
        endDateInput.hidden = !visible;
        endDateLabel.hidden = !visible;
        startDateInput.required = visible;
        endDateInput.required = visible;
    }

    function populateStatusOptions(currentStatus) {
        const allowed = STATUS_TRANSITIONS[currentStatus] || [currentStatus];
        statusInput.replaceChildren();
        allowed.forEach(function (status) {
            const option = document.createElement("option");
            option.value = status;
            option.textContent = STATUS_LABELS[status];
            statusInput.appendChild(option);
        });
        statusInput.value = currentStatus;
    }

    function setStatusFieldVisible(visible, currentStatus) {
        statusInput.hidden = !visible;
        statusLabel.hidden = !visible;
        statusInput.required = visible;
        if (visible) {
            populateStatusOptions(currentStatus);
        } else {
            statusInput.replaceChildren();
        }
        setRescheduleFieldsVisible(visible && currentStatus === "rescheduled");
    }

    function setRescheduleFieldsVisible(visible) {
        rescheduleFields.hidden = !visible;
        [
            rescheduleStartDateInput,
            rescheduleStartTimeInput,
            rescheduleEndDateInput,
            rescheduleEndTimeInput,
        ].forEach(function (input) {
            input.required = visible;
        });
    }

    function openCreateForm(dateStr) {
        editingEventId = null;
        originalEditSnapshot = null;
        autoRescheduleStatus = false;
        selectedDate = dateStr;
        formHeading.textContent = "Schedule an Event";
        selectedDateText.hidden = false;
        selectedDateText.textContent = "Event date: " + selectedDate;
        form.reset();
        errorText.textContent = "";
        saveButton.disabled = false;
        setEditScheduleFieldsVisible(false);
        setStatusFieldVisible(false);
        dialog.showModal();
        titleInput.focus();
    }

    function maybeMarkRescheduled() {
        if (!originalEditSnapshot || originalEditSnapshot.status !== "approved") {
            return;
        }
        const scheduleChanged = isScheduleChanged();
        if (scheduleChanged && statusInput.value === "approved") {
            statusInput.value = "rescheduled";
            autoRescheduleStatus = true;
            rescheduleStartDateInput.value = startDateInput.value;
            rescheduleStartTimeInput.value = startInput.value;
            rescheduleEndDateInput.value = endDateInput.value;
            rescheduleEndTimeInput.value = endInput.value;
            setRescheduleFieldsVisible(true);
        } else if (scheduleChanged && autoRescheduleStatus) {
            rescheduleStartDateInput.value = startDateInput.value;
            rescheduleStartTimeInput.value = startInput.value;
            rescheduleEndDateInput.value = endDateInput.value;
            rescheduleEndTimeInput.value = endInput.value;
        } else if (!scheduleChanged && autoRescheduleStatus) {
            statusInput.value = "approved";
            autoRescheduleStatus = false;
            setRescheduleFieldsVisible(false);
        }
    }

    function isScheduleChanged() {
        return (
            startDateInput.value !== originalEditSnapshot.startDate ||
            endDateInput.value !== originalEditSnapshot.endDate ||
            startInput.value !== originalEditSnapshot.startTime ||
            endInput.value !== originalEditSnapshot.endTime ||
            venueInput.value !== originalEditSnapshot.venue
        );
    }

    function isStartTimeChanged() {
        return (
            startDateInput.value !== originalEditSnapshot.startDate ||
            startInput.value !== originalEditSnapshot.startTime
        );
    }

    function fillFormFromEvent(event) {
        const start = new Date(event.start);
        const end = new Date(event.end);
        const startDate = toLocalDate(start);
        const endDate = toLocalDate(end);
        const startTime = toLocalTime(start);
        const endTime = toLocalTime(end);

        selectedDate = startDate;
        titleInput.value = event.title;
        departmentInput.value = event.department || "";
        venueInput.value = event.venue || "";
        startDateInput.value = startDate;
        endDateInput.value = endDate;
        startInput.value = startTime;
        endInput.value = endTime;
        rescheduleStartDateInput.value = startDate;
        rescheduleStartTimeInput.value = startTime;
        rescheduleEndDateInput.value = endDate;
        rescheduleEndTimeInput.value = endTime;
        rescheduleReasonInput.value = event.rescheduling_reason || "";
        selectedDateText.hidden = true;
        errorText.textContent = "";
        originalEditSnapshot = {
            status: eventStatus(event),
            startDate: startDate,
            endDate: endDate,
            startTime: startTime,
            endTime: endTime,
            venue: event.venue || "",
        };
    }

    function openEditForm(event) {
        editingEventId = event.id;
        autoRescheduleStatus = false;
        formHeading.textContent = "Edit Event";
        form.reset();
        fillFormFromEvent(event);
        saveButton.disabled = false;
        setEditScheduleFieldsVisible(true);
        setStatusFieldVisible(true, eventStatus(event));
        dialog.showModal();
        titleInput.focus();
    }

    function renderStatusList(dateStr, status) {
        const events = eventsForDateAndStatus(dateStr, status);
        statusEventsHeading.textContent =
            STATUS_LABELS[status] + " — " + dateStr;
        statusEventList.replaceChildren();

        if (!events.length) {
            const empty = document.createElement("p");
            empty.className = "empty-events";
            empty.textContent = "No events in this group.";
            statusEventList.appendChild(empty);
            return;
        }

        events.forEach(function (event) {
            const start = new Date(event.start);
            const end = new Date(event.end);
            const currentStatus = eventStatus(event);
            const card = document.createElement("article");
            card.className = "event-card";

            const heading = document.createElement("h2");
            heading.textContent = event.title;

            const departmentLine = document.createElement("p");
            departmentLine.textContent = "Department: " + (event.department || "—");

            const venueLine = document.createElement("p");
            venueLine.append("Venue: ");
            const venueValue = document.createElement("strong");
            venueValue.textContent = venueLabel(event.venue);
            venueLine.appendChild(venueValue);

            const startLine = document.createElement("p");
            startLine.textContent =
                "Start: " + formatDisplayDate(start) + " " + formatDisplayTime(start);

            const endLine = document.createElement("p");
            endLine.textContent =
                "End: " + formatDisplayDate(end) + " " + formatDisplayTime(end);

            const statusLine = document.createElement("p");
            statusLine.className = "event-status " + currentStatus;
            statusLine.textContent = "Status: " + STATUS_LABELS[currentStatus];

            const details = [
                heading,
                departmentLine,
                venueLine,
                startLine,
                endLine,
                statusLine,
            ];
            if (event.rescheduling_reason) {
                const reasonLine = document.createElement("p");
                reasonLine.textContent = "Rescheduling reason: " + event.rescheduling_reason;
                details.push(reasonLine);
            }

            const editButton = document.createElement("button");
            editButton.type = "button";
            editButton.className = "edit-event-btn";
            editButton.textContent = "Edit";
            editButton.addEventListener("click", function () {
                openEditForm(event);
            });

            card.append(
                ...details,
                editButton
            );
            statusEventList.appendChild(card);
        });
    }

    function openStatusList(dateStr, status) {
        listContext = { dateStr: dateStr, status: status };
        renderStatusList(dateStr, status);
        if (!statusEventsDialog.open) {
            statusEventsDialog.showModal();
        }
    }

    calendar = new FullCalendar.Calendar(calendarEl, {
        initialView: "dayGridMonth",
        height: "100%",
        handleWindowResize: true,
        dayMaxEvents: true,

        headerToolbar: {
            left: "prev,next today",
            center: "title",
            right: "dayGridMonth,timeGridWeek,timeGridDay"
        },

        events: function (fetchInfo, successCallback, failureCallback) {
            const deliver = function (events) {
                successCallback(calendarEvents(events));
            };

            if (eventsLoaded) {
                deliver(cachedEvents);
                renderAllSummaries();
                return;
            }

            fetch("/api/events/")
                .then(function (response) {
                    if (!response.ok) {
                        throw new Error("Unable to load events.");
                    }
                    return response.json();
                })
                .then(function (events) {
                    cachedEvents = events;
                    eventsLoaded = true;
                    deliver(cachedEvents);
                    renderAllSummaries();
                })
                .catch(failureCallback);
        },

        datesSet: function () {
            renderAllSummaries();
        },

        dayCellDidMount: function (info) {
            if (currentViewType() !== "dayGridMonth") {
                return;
            }
            renderSummariesForCell(info.el, cellDateStr(info.el, info.date));
        },

        dateClick: function (info) {
            if (info.jsEvent && info.jsEvent.target.closest(".day-status-summaries")) {
                return;
            }
            openCreateForm(info.dateStr);
        }
    });

    calendar.render();

    ["change", "input"].forEach(function (type) {
        venueInput.addEventListener(type, maybeMarkRescheduled);
        startDateInput.addEventListener(type, maybeMarkRescheduled);
        endDateInput.addEventListener(type, maybeMarkRescheduled);
        startInput.addEventListener(type, maybeMarkRescheduled);
        endInput.addEventListener(type, maybeMarkRescheduled);
    });

    document.getElementById("closeStatusEventsBtn").addEventListener("click", function () {
        statusEventsDialog.close();
        listContext = null;
    });

    statusInput.addEventListener("change", function () {
        autoRescheduleStatus = false;
        setRescheduleFieldsVisible(statusInput.value === "rescheduled");
    });

    document.getElementById("cancelEventBtn").addEventListener("click", function () {
        dialog.close();
    });

    form.addEventListener("submit", async function (event) {
        event.preventDefault();
        errorText.textContent = "";
        saveSuccessMessage.hidden = true;

        const title = titleInput.value.trim();
        const department = departmentInput.value.trim();
        const venue = venueInput.value;
        const isEdit = Boolean(editingEventId);
        const startDate = isEdit ? startDateInput.value : selectedDate;
        const endDate = isEdit ? endDateInput.value : selectedDate;
        const startTime = startInput.value;
        const endTime = endInput.value;
        const status = statusInput.value;

        if (!title || !department || !venue || !startDate || !endDate || !startTime || !endTime) {
            errorText.textContent = "Please complete all fields.";
            return;
        }

        if (isEdit && !status) {
            errorText.textContent = "Please complete all fields.";
            return;
        }

        const startLocal = new Date(startDate + "T" + startTime);
        const endLocal = new Date(endDate + "T" + endTime);
        const isRescheduled = isEdit && status === "rescheduled";
        let rescheduleStartLocal = null;
        let rescheduleEndLocal = null;
        if (isRescheduled) {
            if (
                !rescheduleStartDateInput.value ||
                !rescheduleStartTimeInput.value ||
                !rescheduleEndDateInput.value ||
                !rescheduleEndTimeInput.value
            ) {
                errorText.textContent =
                    "Enter the new start and end dates and times to reschedule.";
                return;
            }
            rescheduleStartLocal = new Date(
                rescheduleStartDateInput.value + "T" + rescheduleStartTimeInput.value
            );
            rescheduleEndLocal = new Date(
                rescheduleEndDateInput.value + "T" + rescheduleEndTimeInput.value
            );
            if (!(rescheduleEndLocal > rescheduleStartLocal)) {
                errorText.textContent =
                    "The new end date and time must be later than the new start.";
                return;
            }
        }
        if (
            (isRescheduled && rescheduleStartLocal < new Date()) ||
            (isEdit && !isRescheduled && isStartTimeChanged() && startLocal < new Date())
        ) {
            errorText.textContent =
                "An event cannot be rescheduled to a date and time in the past.";
            return;
        }
        if (!isRescheduled && !(endLocal > startLocal)) {
            errorText.textContent = "End time must be later than start time.";
            return;
        }

        saveButton.disabled = true;
        saveButton.textContent = "Saving...";

        try {
            const url = isEdit ? "/api/events/" + editingEventId + "/" : "/api/events/";
            const payload = {
                title: title,
                department: department,
                venue: venue,
                start: startLocal.toISOString(),
                end: endLocal.toISOString()
            };
            if (isEdit) {
                payload.status = status;
                if (isRescheduled) {
                    payload.reschedule_start = rescheduleStartLocal.toISOString();
                    payload.reschedule_end = rescheduleEndLocal.toISOString();
                    payload.rescheduling_reason = rescheduleReasonInput.value.trim();
                }
            }

            const response = await fetch(url, {
                method: isEdit ? "PUT" : "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": csrfToken()
                },
                body: JSON.stringify(payload)
            });

            if (!response.ok) {
                const result = await response.json();
                throw new Error(result.message || "Unable to save event.");
            }

            const keepListOpen = Boolean(listContext);
            let refreshFailed = false;
            try {
                await reloadEventsFromServer();
            } catch (refreshError) {
                console.error("Event saved but calendar refresh failed:", refreshError);
                refreshFailed = true;
            }
            dialog.close();
            form.reset();
            setEditScheduleFieldsVisible(false);
            setStatusFieldVisible(false);
            editingEventId = null;
            originalEditSnapshot = null;
            if (!keepListOpen) {
                statusEventsDialog.close();
            }
            if (refreshFailed) {
                saveSuccessMessage.textContent =
                    "Event saved, but the calendar could not refresh. Please reload the page.";
            } else if (isRescheduled) {
                saveSuccessMessage.textContent = "Event rescheduled successfully.";
            } else {
                saveSuccessMessage.textContent = "Event saved successfully.";
            }
            saveSuccessMessage.hidden = false;
            window.setTimeout(function () {
                saveSuccessMessage.hidden = true;
            }, 5000);
        } catch (error) {
            console.error("Event save error:", error);
            errorText.textContent = error.message;
        } finally {
            saveButton.disabled = false;
            saveButton.textContent = "Save Event";
        }
    });
});
