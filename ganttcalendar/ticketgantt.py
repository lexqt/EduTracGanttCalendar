import calendar
from datetime import date, timedelta
from genshi.builder import tag
from pkg_resources import resource_filename

from trac.core import Component, implements, TracError
from trac.config import IntOption, BoolOption
from trac.util.datefmt import parse_date_only

from trac.web import IRequestHandler
from trac.web.chrome import INavigationContributor, ITemplateProvider, \
                            add_stylesheet, add_warning

from trac.ticket.api import TicketSystem
from trac.ticket import model

from trac.project.api import ProjectManagement

from ganttcalendar.api import TracGanttCalendar, month_tbl, add_months, date_format, _


__all__ = ['TicketGanttChart']



class TicketGanttChart(Component):

    implements(INavigationContributor, IRequestHandler, ITemplateProvider)

    show_ticket_summary = BoolOption('ganttcalendar', 'show_ticket_summary', 'false',
            doc='Show ticket summary at gantchart bar')
    normal_mode = IntOption('ganttcalendar', 'default_zoom_mode', '3',
            doc='Default zoom mode in gantchar')

    # zoom mode: months term
    zoom_months = {1:1, 2:2, 3:3, 4:4, 5:5, 6:6}

    def __init__(self):
        self.tgc = TracGanttCalendar(self.env)

    # INavigationContributor

    def get_active_navigation_item(self, req):
        return 'ticketgantt'

    def get_navigation_items(self, req):
        if req.perm.has_permission('TICKET_VIEW'):
            yield ('mainnav', 'ticketgantt',tag.a(_('Gantt chart'), href=req.href.ticketgantt()))

    # IRequestHandler

    def match_request(self, req):
        return req.path_info.startswith('/ticketgantt')

    def process_request(self, req):

        req.perm.require('TICKET_VIEW')

        ymonth  = req.args.getint('month')
        yyear   = req.args.getint('year')
        baseday = req.args.get('baseday')

        selected_milestone = req.args.get('selected_milestone')
        selected_component = req.args.get('selected_component')
        sorted_field       = req.args.get('sorted_field', 'milestone')

        show_my_ticket     = req.args.getbool('show_my_ticket', False)
        show_closed_ticket = not req.args.getbool('hide_closed_ticket', False)

        show_ticket_summary = req.args.getbool('show_ticket_summary', self.show_ticket_summary)
        show_ticket_status  = not req.args.getbool('hide_ticket_status', False)

        pm = ProjectManagement(self.env)
        pid = pm.get_and_check_current_project(req, allow_multi=True)

        fields = TicketSystem(self.env).get_ticket_fields(pid=pid)
        time_fields = []
        custom_fields = []
        for n, f in fields.iteritems():
            if f['type'] == 'time':
                time_fields.append(n)
            if f.get('custom'):
                custom_fields.append(n)

        if 'complete' not in custom_fields:
            add_warning(req, _("'complete' field is not defined. Please, check your configuration."))

        current_mode = req.args.getint('zoom', self.normal_mode)
        if current_mode < 1 or current_mode > 6:
            current_mode = self.normal_mode

        
        months_term  = self.zoom_months[current_mode]

        first_wkday = (7 + self.tgc.first_day - 1) % 7

        if baseday:
            try:
                baseday = parse_date_only(baseday)
            except TracError:
                baseday = None
        if not baseday:
            baseday = date.today()

        ticket_margin = 12 if show_ticket_summary else 0

        if ymonth and yyear:
            cday = date(yyear, ymonth, 1)
        else:
            cday = date.today()

        # next and previous months
        nmonth = add_months(cday.year, cday.month, 1)
        pmonth = add_months(cday.year, cday.month, -1)

        first_date = cday.replace(day=1)
        last_date  = add_months(cday.year, cday.month, months_term) - timedelta(1)
        days_term  = ( (first_date + timedelta(months_term*32)).replace(day=1) - first_date ).days

        # process ticket
        db = self.env.get_read_db()
        cursor = db.cursor();
        conditions = []
        args = []

        conditions.append('t.project_id = %s')
        args.append(pid)

        conditions.append("(a.due_assign, c.due_close + INTERVAL '1 DAY')"
                          " OVERLAPS (DATE '%s', DATE '%s')" % (
                          first_date.isoformat(), last_date.isoformat()))

        if show_my_ticket:
            conditions.append('owner=%s')
            args.append(req.authname)
        if not show_closed_ticket:
            conditions.append("status <> 'closed'")
        if selected_milestone:
            conditions.append('milestone=%s')
            args.append(selected_milestone)
        if selected_component:
            conditions.append('component=%s')
            args.append(selected_component)

        condition = "WHERE " + ' AND '.join(conditions)
            
        sql = '''
            SELECT id, type, summary, owner, t.description, status, resolution, priority,
                   a.due_assign, c.due_close,
                   cmp.value, est.value, tot.value, milestone, component
            FROM ticket t
            JOIN (
                SELECT ticket, CAST(value AS DATE) AS due_assign
                FROM ticket_custom
                WHERE name = 'due_assign' AND value IS NOT NULL
            ) a ON a.ticket = t.id
            JOIN (
                SELECT ticket, CAST(value AS DATE) AS due_close
                FROM ticket_custom
                WHERE name = 'due_close' AND value IS NOT NULL
            ) c ON c.ticket = t.id
            JOIN ticket_custom cmp ON cmp.ticket = t.id AND cmp.name = 'complete'
            LEFT OUTER JOIN ticket_custom est ON est.ticket = t.id AND est.name = 'estimatedhours'
            LEFT OUTER JOIN ticket_custom tot ON tot.ticket = t.id AND tot.name = 'totalhours'
            %s
            ORDER by %s, a.due_assign
            ''' % (condition, db.quote(sorted_field))
        
        self.log.debug(sql)
        cursor.execute(sql, args)

        time_tracking = 'estimatedhours' in fields
        sum_estimatedhours = 0.0
        sum_totalhours = 0.0

        tickets=[]
        for id_, type_, summary, owner, description, status, resolution, priority, due_assign, due_close, complete, estimatedhours, totalhours, milestone, component in cursor:
            due_assign_date = due_assign
            due_close_date  = due_close
            complete        = model.convert_field_value(fields.get('complete'), complete, 0)

            if not due_assign_date or not due_close_date or due_assign_date > due_close_date:
                continue
            if not milestone:
                milestone = "*"
            if not component:
                component = "*"

            # time tracking
            if time_tracking:
                estimatedhours = model.convert_field_value(fields.get('estimatedhours'), estimatedhours, 0.0)
                totalhours = model.convert_field_value(fields.get('totalhours'), totalhours, 0.0)
                sum_estimatedhours += estimatedhours
                sum_totalhours += totalhours

            ticket = {'id':id_, 'type':type_, 'summary':summary, 'owner':owner, 'description': description, 'status':status,
                    'resolution':resolution, 'priority':priority,
                    'due_assign':due_assign_date, 'due_close':due_close_date, 'complete': complete, 
                    'estimatedhours':estimatedhours, 'totalhours':totalhours,
                    'milestone': milestone,'component': component}

            #calc chart
            base = (baseday -first_date).days + 1
            done_start = done_end = None
            late_start = late_end = None
            todo_start = todo_end = None
            all_start = (due_assign_date-first_date).days
            all_end   = (due_close_date-first_date).days + 1
            done_start = all_start
            done_end   = done_start + (all_end - all_start) * complete / 100.0
            if all_end <= base:
                late_start = done_end
                late_end   = all_end
            elif done_end <= base < all_end:
                late_start = done_end
                late_end   = todo_start= base
                todo_end= all_end
            else:
                todo_start = done_end
                todo_end   = all_end
            #
            done_start, done_end = self.adjust(done_start, done_end, days_term)
            late_start, late_end = self.adjust(late_start, late_end, days_term)
            todo_start, todo_end = self.adjust(todo_start, todo_end, days_term)
            all_start,  all_end  = self.adjust(all_start,  all_end,  days_term)

            if done_start != None:
                ticket.update({'done_start':done_start,'done_end':done_end})
            if late_start != None:
                ticket.update({'late_start':late_start,'late_end':late_end})
            if todo_start != None:
                ticket.update({'todo_start':todo_start,'todo_end':todo_end})
            if all_start != None:
                ticket.update({'all_start':all_start,'all_end':all_end})

            self.log.debug(ticket)
            tickets.append(ticket)

        # time tracking
        if not time_tracking:
            sum_estimatedhours = None

        # milestones
        milestones = {'':None}
        milestones_list = model.Milestone.select(self.env, pid=pid, db=db)
        for m in milestones_list:
            d = m.due
            if d:
                d = d.date()
            milestones[m.name] = {
                'due': d,
                'description': m.description,
            }

        # components
        components = list(model.Component.select(self.env, pid=pid, db=db))

        data = {
            'baseday': baseday, 'current':cday, 'prev':pmonth, 'next':nmonth, 'month_tbl': month_tbl,
            'show_my_ticket': show_my_ticket, 'show_closed_ticket': show_closed_ticket, 'sorted_field': sorted_field,
            'show_ticket_summary': show_ticket_summary, 'show_ticket_status': show_ticket_status, 'ti_mrgn': ticket_margin,
            'selected_milestone':selected_milestone,'selected_component': selected_component,
            'tickets':tickets,'milestones':milestones,'components':components,
            'sum_estimatedhours':sum_estimatedhours, 'sum_totalhours':sum_totalhours,
            'first_date':first_date,'days_term':days_term,
            'calendar':calendar,
            'date_format': date_format ,'first_wkday':first_wkday,'normal':self.normal_mode,'zoom':current_mode,
            '_':_,
        }

        add_stylesheet(req, 'ganttchart/css/chart.css')

        return 'gantt.html', data, None

    # ITemplateProvider

    def get_templates_dirs(self):
        return [resource_filename(__name__, 'templates')]

    def get_htdocs_dirs(self):
        return [('ganttchart', resource_filename(__name__, 'htdocs'))]

    #

    def adjust( self, x_start, x_end, term):
        if x_start > term or x_end < 0:
            x_start= None
        else:
            if x_start < 0:
                x_start= 0
            if x_end > term:
                x_end= term
        return x_start, x_end

