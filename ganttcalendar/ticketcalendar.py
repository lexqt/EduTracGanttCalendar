import calendar
from datetime import date, timedelta

from genshi.builder import tag

from trac.core import Component, implements
from trac.web import IRequestHandler
from trac.web.chrome import INavigationContributor, add_stylesheet
from trac.config import BoolOption

from trac.ticket.api import TicketSystem, convert_field_value
from trac.ticket import model

from trac.project.api import ProjectManagement

from ganttcalendar.api import TracGanttCalendar, month_tbl, weekdays, date_format, _


__all__ = ['TicketCalendar']



class TicketCalendar(Component):

    implements(INavigationContributor, IRequestHandler)

    show_weekly_view = BoolOption('ganttcalendar', 'show_weekly_view', 'false',
            doc='Set weekly view as default in calendar.')

    def __init__(self):
        self.tgc = TracGanttCalendar(self.env)

    # INavigationContributor

    def get_active_navigation_item(self, req):
        return 'ticketcalendar'

    def get_navigation_items(self, req):
        if req.perm.has_permission('TICKET_VIEW'):
            yield ('mainnav', 'ticketcalendar',tag.a(_('Calendar'), href=req.href.ticketcalendar()))

    # IRequestHandler

    def match_request(self, req):
        return req.path_info.startswith('/ticketcalendar')

    def calendarRange(self, y, m, wk):
        calendar.setfirstweekday(wk)
        li = calendar.monthcalendar(y,m)
        days = li[0].count(0)
        firstDay = date(y,m,1) - timedelta(days)
        days = li[-1].count(0)
        lastDay = date(y,m,max(li[-1])) + timedelta(days)
        return firstDay, lastDay

    def process_request(self, req):
        req.perm.require('TICKET_VIEW')

        year  = req.args.getint('year')
        month = req.args.getint('month')
        day   = req.args.getint('day', 1)
        weekly_view = req.args.getint('weekly', 0)

        show_my_ticket     = req.args.getbool('show_my_ticket', False)
        show_closed_ticket = not req.args.getbool('hide_closed_ticket', False)

        selected_milestone = req.args.get('selected_milestone')

        pm = ProjectManagement(self.env)
        pid = pm.get_current_project(req)

        fields = TicketSystem(self.env).get_ticket_fields(pid=pid)

        if year and month:
            cday = date(int(year),int(month),int(day))
        else:
            cday = date.today()
            show_closed_ticket = 'on'
            weekly_view = int(self.show_weekly_view)

        first_wkday = (7 + self.tgc.first_day - 1) % 7
        first, last = self.calendarRange(cday.year, cday.month, first_wkday)

        if weekly_view:
            first = first + timedelta(weeks=(cday-first).days/7)
            last = first + timedelta(days=6)
            prev = first - timedelta(weeks=1)
            next = first + timedelta(weeks=1)
        else:
            prev = cday.replace(day=1).__add__(timedelta(days=-1)).replace(day=1)
            next = cday.replace(day=1).__add__(timedelta(days=32)).replace(day=1)

        conditions = []
        args = []

        conditions.append('t.project_id = %s')
        args.append(pid)

        conditions.append("(a.due_assign, c.due_close + INTERVAL '1 DAY')"
                          " OVERLAPS (DATE '%s', DATE '%s')" % (
                          first.isoformat(), last.isoformat()))

        if show_my_ticket:
            conditions.append('owner=%s')
            args.append(req.authname)
        if not show_closed_ticket:
            conditions.append("status <> 'closed'")
        if selected_milestone:
            conditions.append('milestone=%s')
            args.append(selected_milestone)

        db = self.env.get_read_db()
        cursor = db.cursor();

        condition = "WHERE " + ' AND '.join(conditions)

        sql = '''
            SELECT id, type, summary, owner, description, status, resolution, priority,
                   a.due_assign, c.due_close,
                   cmp.value, est.value, tot.value from ticket t
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
            ''' % (condition,)

        self.log.debug(sql)
        cursor.execute(sql, args)

        time_tracking = 'estimatedhours' in fields
        sum_estimatedhours = 0.0
        sum_totalhours = 0.0

        tickets=[]
        for id, type, summary, owner, description, status, resolution, priority, due_assign, due_close, complete, estimatedhours, totalhours in cursor:
            due_assign_date = due_assign
            due_close_date  = due_close
            complete        = convert_field_value(fields.get('complete'), complete, 0)

            if not due_assign_date or not due_close_date or due_assign_date > due_close_date:
                continue

            # time tracking
            if time_tracking:
                estimatedhours = convert_field_value(fields.get('estimatedhours'), estimatedhours, 0.0)
                totalhours = convert_field_value(fields.get('totalhours'), totalhours, 0.0)
                sum_estimatedhours += estimatedhours
                sum_totalhours += totalhours

            ticket = {'id':id, 'type':type, 'summary':summary, 'owner':owner, 'description': description,
                      'status':status, 'resolution':resolution, 'priority':priority,
                      'due_assign':due_assign_date, 'due_close':due_close_date, 'complete': complete,
                      'estimatedhours':estimatedhours, 'totalhours':totalhours}
            tickets.append(ticket)

        # time tracking
        if not time_tracking:
            sum_estimatedhours = None

        # milestones
        milestones = [{}]
        milestones_list = model.Milestone.select(self.env, pid=pid, db=db)
        for m in milestones_list:
            d = m.due
            if d:
                d = d.date()
            milestones.append({
                'name': m.name,
                'due': d,
                'completed': bool(m.completed),
                'description': m.description,
            })

        #days
        days = {}
        for d in range((last-first).days+1):
            mday= first + timedelta(d)
            days[mday] = {}
            #day kind
            if mday == date.today():
                kind = 'today'
            elif mday.weekday() in (5,6):
                kind = 'holiday'
            else:
                kind = 'active'
            days[mday]['kind'] = kind
            #ticket
            days[mday]['ticket']=[]
            for t in range(len(tickets)):
                if mday == tickets[t]['due_assign'] == tickets[t]['due_close']:
                    days[mday]['ticket'].append({'img':'bw','num':t})
                elif mday == tickets[t]['due_assign']:
                    days[mday]['ticket'].append({'img':'from','num':t})
                elif mday == tickets[t]['due_close']:
                    days[mday]['ticket'].append({'img':'to','num':t})
            #milestone
            days[mday]['milestone'] = []
            for m in range(len(milestones)):
                if mday == milestones[m].get('due'):
                    days[mday]['milestone'].append(m)

        data = {'current':cday, 'prev':prev, 'next':next, 'weekly':weekly_view, 'first':first, 'last':last,
                'tickets':tickets, 'milestones':milestones,'days':days,
                'sum_estimatedhours':sum_estimatedhours, 'sum_totalhours':sum_totalhours,
                'show_my_ticket': show_my_ticket, 'show_closed_ticket': show_closed_ticket, 'selected_milestone': selected_milestone,
                '_':_,'date_format':date_format, 'month_tbl': month_tbl, 'weekdays': weekdays}

        add_stylesheet(req, 'ganttcalendar/css/calendar.css')

        return 'calendar.html', data, None

