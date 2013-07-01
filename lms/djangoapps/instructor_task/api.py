"""
API for submitting background tasks by an instructor for a course.

Also includes methods for getting information about tasks that have
already been submitted, filtered either by running state or input
arguments.

"""

from celery.states import READY_STATES

from xmodule.modulestore.django import modulestore

from instructor_task.models import InstructorTask
from instructor_task.tasks import (rescore_problem,
                                   reset_problem_attempts,
                                   delete_problem_state,
                                   update_offline_grades)

from instructor_task.api_helper import (check_arguments_for_rescoring,
                                        encode_problem_and_student_input,
                                        submit_task)


def get_running_instructor_tasks(course_id):
    """
    Returns a query of InstructorTask objects of running tasks for a given course.

    Used to generate a list of tasks to display on the instructor dashboard.
    """
    instructor_tasks = InstructorTask.objects.filter(course_id=course_id)
    # exclude states that are "ready" (i.e. not "running", e.g. failure, success, revoked):
    for state in READY_STATES:
        instructor_tasks = instructor_tasks.exclude(task_state=state)
    return instructor_tasks.order_by('-id')


def get_instructor_task_history(course_id, problem_url=None, student=None, task_type=None):
    """
    Returns a query of InstructorTask objects of historical tasks for a given course,
    that optionally match a particular problem, a student, and/or a task type.
    """
    instructor_tasks = InstructorTask.objects.filter(course_id=course_id)
    if problem_url is not None or student is not None:
        _, task_key = encode_problem_and_student_input(problem_url, student)
        instructor_tasks = instructor_tasks.filter(task_key=task_key)
    if task_type is not None:
        instructor_tasks = instructor_tasks.filter(task_type=task_type)

    return instructor_tasks.order_by('-id')


def submit_rescore_problem_for_student(request, course_id, problem_url, student):
    """
    Request a problem to be rescored as a background task.

    The problem will be rescored for the specified student only.  Parameters are the `course_id`,
    the `problem_url`, and the `student` as a User object.
    The url must specify the location of the problem, using i4x-type notation.

    ItemNotFoundException is raised if the problem doesn't exist, or AlreadyRunningError
    if the problem is already being rescored for this student, or NotImplementedError if
    the problem doesn't support rescoring.

    This method makes sure the InstructorTask entry is committed.
    When called from any view that is wrapped by TransactionMiddleware,
    and thus in a "commit-on-success" transaction, an autocommit buried within here
    will cause any pending transaction to be committed by a successful
    save here.  Any future database operations will take place in a
    separate transaction.

    """
    # check arguments:  let exceptions return up to the caller.
    check_arguments_for_rescoring(course_id, problem_url)

    task_type = 'rescore_problem'
    task_class = rescore_problem
    task_input, task_key = encode_problem_and_student_input(problem_url, student)
    return submit_task(request, task_type, task_class, course_id, task_input, task_key)


def submit_rescore_problem_for_all_students(request, course_id, problem_url):
    """
    Request a problem to be rescored as a background task.

    The problem will be rescored for all students who have accessed the
    particular problem in a course and have provided and checked an answer.
    Parameters are the `course_id` and the `problem_url`.
    The url must specify the location of the problem, using i4x-type notation.

    ItemNotFoundException is raised if the problem doesn't exist, or AlreadyRunningError
    if the problem is already being rescored, or NotImplementedError if the problem doesn't
    support rescoring.

    This method makes sure the InstructorTask entry is committed.
    When called from any view that is wrapped by TransactionMiddleware,
    and thus in a "commit-on-success" transaction, an autocommit buried within here
    will cause any pending transaction to be committed by a successful
    save here.  Any future database operations will take place in a
    separate transaction.
    """
    # check arguments:  let exceptions return up to the caller.
    check_arguments_for_rescoring(course_id, problem_url)

    # check to see if task is already running, and reserve it otherwise
    task_type = 'rescore_problem'
    task_class = rescore_problem
    task_input, task_key = encode_problem_and_student_input(problem_url)
    return submit_task(request, task_type, task_class, course_id, task_input, task_key)


def submit_reset_problem_attempts_for_all_students(request, course_id, problem_url):
    """
    Request to have attempts reset for a problem as a background task.

    The problem's attempts will be reset for all students who have accessed the
    particular problem in a course.  Parameters are the `course_id` and
    the `problem_url`.  The url must specify the location of the problem,
    using i4x-type notation.

    ItemNotFoundException is raised if the problem doesn't exist, or AlreadyRunningError
    if the problem is already being reset.

    This method makes sure the InstructorTask entry is committed.
    When called from any view that is wrapped by TransactionMiddleware,
    and thus in a "commit-on-success" transaction, an autocommit buried within here
    will cause any pending transaction to be committed by a successful
    save here.  Any future database operations will take place in a
    separate transaction.
    """
    # check arguments:  make sure that the problem_url is defined
    # (since that's currently typed in).  If the corresponding module descriptor doesn't exist,
    # an exception will be raised.  Let it pass up to the caller.
    modulestore().get_instance(course_id, problem_url)

    task_type = 'reset_problem_attempts'
    task_class = reset_problem_attempts
    task_input, task_key = encode_problem_and_student_input(problem_url)
    return submit_task(request, task_type, task_class, course_id, task_input, task_key)


def submit_delete_problem_state_for_all_students(request, course_id, problem_url):
    """
    Request to have state deleted for a problem as a background task.

    The problem's state will be deleted for all students who have accessed the
    particular problem in a course.  Parameters are the `course_id` and
    the `problem_url`.  The url must specify the location of the problem,
    using i4x-type notation.

    ItemNotFoundException is raised if the problem doesn't exist, or AlreadyRunningError
    if the particular problem's state is already being deleted.

    This method makes sure the InstructorTask entry is committed.
    When called from any view that is wrapped by TransactionMiddleware,
    and thus in a "commit-on-success" transaction, an autocommit buried within here
    will cause any pending transaction to be committed by a successful
    save here.  Any future database operations will take place in a
    separate transaction.
    """
    # check arguments:  make sure that the problem_url is defined
    # (since that's currently typed in).  If the corresponding module descriptor doesn't exist,
    # an exception will be raised.  Let it pass up to the caller.
    modulestore().get_instance(course_id, problem_url)

    task_type = 'delete_problem_state'
    task_class = delete_problem_state
    task_input, task_key = encode_problem_and_student_input(problem_url)
    return submit_task(request, task_type, task_class, course_id, task_input, task_key)


def submit_update_offline_grades(request, course_id):
    """
    Request to have state deleted for a problem as a background task.

    The offline grades will be updated for all students who have enrolled
    in a course.  Parameters are the `course_id`.

    AlreadyRunningError is raised if the course's grades are already being updated.

    This method makes sure the InstructorTask entry is committed.
    When called from any view that is wrapped by TransactionMiddleware,
    and thus in a "commit-on-success" transaction, an autocommit buried within here
    will cause any pending transaction to be committed by a successful
    save here.  Any future database operations will take place in a
    separate transaction.
    """
    # check arguments:  make sure that the course is defined?
    # TODO: what is the right test here?
    # modulestore().get_instance(course_id, problem_url)

    task_type = 'update_offline_grades'
    task_class = update_offline_grades
    # TODO: figure out if we need to encode in a standard way, or if we can get away
    # with doing this manually.  Shouldn't be hard to make the encode call explicitly,
    # and allow no problem_url or student to be defined.  Like this:
    # task_input, task_key = encode_problem_and_student_input()
    task_input = {}
    task_key = ""
    return submit_task(request, task_type, task_class, course_id, task_input, task_key)
