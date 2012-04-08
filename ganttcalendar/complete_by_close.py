import datetime

from trac.core import Component, implements
from trac.config import ListOption
from trac.ticket import ITicketChangeListener


__all__ = ['GanttCompleteTicketObserver']



class GanttCompleteTicketObserver(Component):

    implements(ITicketChangeListener)

    complete_conditions = ListOption('ganttcalendar', 'complete_conditions', 'done, fixed, invalid',
        doc='The resolutions to change the ticket progress to 100% when ticket closed', switcher=True)

    def ticket_created(self, ticket):
        """Called when a ticket is created."""
        self.watch_complete(ticket, {})

    def ticket_changed(self, ticket, comment, author, old_values):
        """Called when a ticket is modified.

        `old_values` is a dictionary containing the previous values of the
        fields that have changed.
        """
        self.watch_complete(ticket, old_values)

    def ticket_deleted(self, ticket):
        """Called when a ticket is deleted."""
        pass

    def watch_complete(self, ticket, old_values):
        complete = ticket['complete']
        if complete is None or complete == 100:
            return;

        oldstatus  = old_values.get('status')
        status     = ticket['status']
        resolution = ticket['resolution']

        if not oldstatus or status != 'closed':
            return

        syllabus_id = ticket.syllabus_id
        complete_conditions = self.complete_conditions.syllabus(syllabus_id)

        # complete by close
        if resolution in complete_conditions:
            ticket['complete'] = 100

