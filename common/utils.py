# apps/users/utils.py
from django.contrib.auth.models import Permission, Group  # noqa
from django.contrib.auth import get_user_model
User = get_user_model()

def is_member(user, group):
    return user.groups.filter(name=group).exists()

def is_in_multiple_groups(user, groups=dict):
    return user.groups.filter(name__in=groups).exists()    

def add_group(user, group_name, auto=False):
    if auto:
        try:
            group, _ = Group.objects.get_or_create(name=group_name)
        except Exception as e:
            return
    else:
        try:
            group = Group.objects.get(name=group_name)
        except Exception as e:
            return
            
    # assign group to user
    user.groups.add(group) 

def get_selected_user(request):
    """Utility function to retrieve the selected user based on request parameters."""
    selected_user = request.GET.get('selectedUser')  #TODO user_id
    
    if selected_user:
        try:
            selected_user = User.objects.get(username=selected_user)
        except User.DoesNotExist:
            pass
    
    return selected_user

def get_org_units(org_unit_id=None, filter_kwargs=None, annotate_kwargs=None):
    """
    Retrieves and processes organizational units and returns:
    - root_nodes: OrgUnit instances that are root nodes (depth=1).
    - all_nodes_dict: All OrgUnit instances annotated with counts or any other additional fields.
    - selected_org_unit: The OrgUnit instance selected by org_unit_id (if valid).

    Args:
        org_unit_id (int, optional): The ID of the organizational unit to select.
        filter_kwargs (dict, optional): Additional filter criteria for the OrgUnit queryset.
        annotate_kwargs (dict, optional): Annotations to apply to the OrgUnit queryset.

    Returns:
        tuple: (root_nodes, all_nodes_dict, selected_org_unit)
    """
    from .models import OrgUnit
    # Prepare the queryset with optional annotations and filters
    queryset = OrgUnit.objects.all()
    if annotate_kwargs:
        queryset = queryset.annotate(**annotate_kwargs)
    if filter_kwargs:
        queryset = queryset.filter(**filter_kwargs)

    # Fetch all nodes and filter root nodes
    all_nodes = queryset
    # Filter manually for depth = 1 (i.e., root nodes)
    # root_nodes = all_nodes.filter(depth=1)  #with treebeard, below w/o treebeard
    root_nodes = [org_unit for org_unit in all_nodes if org_unit.depth == 1]

    # Find selected organization unit by ID
    selected_org_unit = None
    if org_unit_id:
        try:
            selected_org_unit = OrgUnit.objects.get(id=org_unit_id)
        except (ValueError, TypeError, OrgUnit.DoesNotExist):
            selected_org_unit = None

    # Convert all nodes to a dictionary keyed by their IDs
    all_nodes_dict = {node.id: node for node in all_nodes}

    return root_nodes, all_nodes_dict, selected_org_unit


def get_org_units_hierarchy(root_nodes, all_nodes_dict, selected_org_unit=None, selected_o_year=None, max_depth=2):
    """
    Build a hierarchical dictionary of organizational units with objective counts.

    Args:
        root_nodes (QuerySet): The root nodes of organizational units.
        all_nodes_dict (dict): A dictionary of all OrgUnit instances keyed by their IDs.
        selected_org_unit (OrgUnit, optional): The OrgUnit instance to start hierarchy from.
        selected_o_year (int, optional): The year to filter objectives.
        max_depth (int): Maximum depth to display in the hierarchy (default is 2).

    Returns:
        dict: A dictionary representing the hierarchical structure of organizational units, including objective counts.
    """

    def build_hierarchy(node_id, parent=None, depth=0):
        """ Recursively build hierarchy of nodes with a depth limit """
        if depth >= max_depth:
            return {}
        node = all_nodes_dict.get(node_id)
        if not node:
            return {}

        # Get the pre-computed objective count for this node
        count = getattr(node, 'count', 0)  # Use pre-computed count if available
        rolled_counts = count  # current node to be add up 
        
        # Get children nodes
        if depth == (max_depth-1):
            children_dict = None
        else:    
            children = node.get_children()
            # Create a dictionary of child nodes, no parent need
            children_dict = {child.id: build_hierarchy(child.id, None, depth + 1) for child in children}

        return {
            'node': node,  # The current node
            'parent': parent,  # Reference to the parent for top node only
            'count': count,  # Count for this node
            'rolled_counts': rolled_counts,
            'children': children_dict  # The children nodes
        }

    hierarchy = {}

    # If a selected org unit is provided, start hierarchy from it
    if selected_org_unit:
        hierarchy[selected_org_unit.id] = build_hierarchy(selected_org_unit.id, parent=selected_org_unit.parent_id)
    else:
        # Otherwise, build hierarchy for all root nodes
        for root in root_nodes:
            hierarchy[root.id] = build_hierarchy(root.id)

    return hierarchy

