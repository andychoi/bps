# views.decorator.py
from rest_framework.response import Response
from .models.models import PlanningSession

# pseudo‐decorator
def require_stage(stage_code):
    def decorator(fn):
        def wrapped(self, request, *args, **kw):
            # fetch session from URL or param
            sess = PlanningSession.objects.get(pk=kw.get('session_id'))
            if sess.current_stage.code != stage_code \
               and not sess.current_stage.can_run_in_parallel:
                return Response(
                    {"detail": f"Must be in {stage_code} step to call this."},
                    status=403
                )
            return fn(self, request, *args, **kw)
        return wrapped
    return decorator

"""usage
class ManualPlanningAPIView(APIView):
    @require_stage('MANUAL_ORG')
    def post(self, request, ...):
        # handle manual planning edits

"""
