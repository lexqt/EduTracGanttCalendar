from trac.core import Component, implements
from trac.ticket import ITicketManipulator

from ganttcalendar.api import _


__all__ = ['GanttTicketValidator']



class GanttTicketValidator(Component):

    implements(ITicketManipulator)

    def prepare_ticket(self, req, ticket, fields, actions):
        pass

    def validate_ticket(self, req, ticket, action):
        errors = []

        due_assign = ticket['due_assign']
        due_close  = ticket['due_close']
        if due_assign and due_close and due_assign > due_close:
            errors.append(('due_close', _('Close date must not be less than assign date')))

        complete = ticket.values.get('complete')
        if complete:
            if complete < 0 or complete > 100:
                errors.append(('complete',
                               _("'%(val)s' is invalid value. It must be integer in the range from 0 to 100", val=complete) ))
            if not ticket.exists and complete > 0:
                errors.append(('complete',
                               _('Value must be 0 for new tickets') ))

        return errors
