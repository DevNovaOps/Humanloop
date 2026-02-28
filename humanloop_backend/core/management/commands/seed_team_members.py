"""
Management command to seed 100 team members for NSS-Vadodara NGO
and assign them to pilots proportionally based on expected_members.

Usage: python manage.py seed_team_members
"""
import math
from django.core.management.base import BaseCommand
from core.models import User, OrgMember, Pilot, TeamMember


# 100 Indian team members with roles
TEAM_DATA = [
    # 10 Team Leads
    ("Aarav Sharma", "aarav.sharma@humanloop.org", "lead"),
    ("Priya Patel", "priya.patel@humanloop.org", "lead"),
    ("Rohan Mehta", "rohan.mehta@humanloop.org", "lead"),
    ("Ananya Iyer", "ananya.iyer@humanloop.org", "lead"),
    ("Vikram Singh", "vikram.singh@humanloop.org", "lead"),
    ("Sneha Nair", "sneha.nair@humanloop.org", "lead"),
    ("Arjun Reddy", "arjun.reddy@humanloop.org", "lead"),
    ("Kavita Deshmukh", "kavita.deshmukh@humanloop.org", "lead"),
    ("Aditya Joshi", "aditya.joshi@humanloop.org", "lead"),
    ("Meera Kulkarni", "meera.kulkarni@humanloop.org", "lead"),

    # 5 Data Analysts
    ("Rahul Verma", "rahul.verma@humanloop.org", "data_analyst"),
    ("Divya Chatterjee", "divya.chatterjee@humanloop.org", "data_analyst"),
    ("Karan Malhotra", "karan.malhotra@humanloop.org", "data_analyst"),
    ("Pooja Gupta", "pooja.gupta@humanloop.org", "data_analyst"),
    ("Nikhil Bhatia", "nikhil.bhatia@humanloop.org", "data_analyst"),

    # 5 Budget Managers
    ("Shreya Kapoor", "shreya.kapoor@humanloop.org", "budget_manager"),
    ("Manish Tiwari", "manish.tiwari@humanloop.org", "budget_manager"),
    ("Ritu Agarwal", "ritu.agarwal@humanloop.org", "budget_manager"),
    ("Siddharth Rao", "siddharth.rao@humanloop.org", "budget_manager"),
    ("Neha Saxena", "neha.saxena@humanloop.org", "budget_manager"),

    # 5 Community Organizers
    ("Amit Pandey", "amit.pandey@humanloop.org", "community_organizer"),
    ("Ishita Banerjee", "ishita.banerjee@humanloop.org", "community_organizer"),
    ("Deepak Chauhan", "deepak.chauhan@humanloop.org", "community_organizer"),
    ("Tanvi Mishra", "tanvi.mishra@humanloop.org", "community_organizer"),
    ("Rajesh Kumar", "rajesh.kumar@humanloop.org", "community_organizer"),

    # 10 Field Coordinators
    ("Pallavi Srinivasan", "pallavi.srinivasan@humanloop.org", "field_coordinator"),
    ("Gaurav Thakur", "gaurav.thakur@humanloop.org", "field_coordinator"),
    ("Simran Kaur", "simran.kaur@humanloop.org", "field_coordinator"),
    ("Harsh Dubey", "harsh.dubey@humanloop.org", "field_coordinator"),
    ("Aditi Mukherjee", "aditi.mukherjee@humanloop.org", "field_coordinator"),
    ("Vivek Choudhary", "vivek.choudhary@humanloop.org", "field_coordinator"),
    ("Swati Pillai", "swati.pillai@humanloop.org", "field_coordinator"),
    ("Pranav Gokhale", "pranav.gokhale@humanloop.org", "field_coordinator"),
    ("Nidhi Bhatt", "nidhi.bhatt@humanloop.org", "field_coordinator"),
    ("Suresh Menon", "suresh.menon@humanloop.org", "field_coordinator"),

    # 65 Members
    ("Ankita Rawat", "ankita.rawat@humanloop.org", "member"),
    ("Varun Khanna", "varun.khanna@humanloop.org", "member"),
    ("Megha Dasgupta", "megha.dasgupta@humanloop.org", "member"),
    ("Tushar Patil", "tushar.patil@humanloop.org", "member"),
    ("Jyoti Hegde", "jyoti.hegde@humanloop.org", "member"),
    ("Abhishek Soni", "abhishek.soni@humanloop.org", "member"),
    ("Ritika Sethi", "ritika.sethi@humanloop.org", "member"),
    ("Naveen Prasad", "naveen.prasad@humanloop.org", "member"),
    ("Lakshmi Venkatesh", "lakshmi.venkatesh@humanloop.org", "member"),
    ("Kunal Awasthi", "kunal.awasthi@humanloop.org", "member"),
    ("Bhavna Rathore", "bhavna.rathore@humanloop.org", "member"),
    ("Sachin Deshpande", "sachin.deshpande@humanloop.org", "member"),
    ("Kriti Mahajan", "kriti.mahajan@humanloop.org", "member"),
    ("Ajay Narayanan", "ajay.narayanan@humanloop.org", "member"),
    ("Sapna Trivedi", "sapna.trivedi@humanloop.org", "member"),
    ("Dhruv Solanki", "dhruv.solanki@humanloop.org", "member"),
    ("Preeti Jain", "preeti.jain@humanloop.org", "member"),
    ("Mohit Yadav", "mohit.yadav@humanloop.org", "member"),
    ("Aishwarya Nambiar", "aishwarya.nambiar@humanloop.org", "member"),
    ("Tarun Bhardwaj", "tarun.bhardwaj@humanloop.org", "member"),
    ("Sonali Dutta", "sonali.dutta@humanloop.org", "member"),
    ("Pankaj Srivastava", "pankaj.srivastava@humanloop.org", "member"),
    ("Komal Oberoi", "komal.oberoi@humanloop.org", "member"),
    ("Yash Parmar", "yash.parmar@humanloop.org", "member"),
    ("Rashmi Gowda", "rashmi.gowda@humanloop.org", "member"),
    ("Akash Tripathi", "akash.tripathi@humanloop.org", "member"),
    ("Shikha Ranganathan", "shikha.ranganathan@humanloop.org", "member"),
    ("Mayank Purohit", "mayank.purohit@humanloop.org", "member"),
    ("Tanya Bose", "tanya.bose@humanloop.org", "member"),
    ("Saurabh Wagh", "saurabh.wagh@humanloop.org", "member"),
    ("Anjali Subramaniam", "anjali.subramaniam@humanloop.org", "member"),
    ("Rohit Shekhawat", "rohit.shekhawat@humanloop.org", "member"),
    ("Nikita Pandit", "nikita.pandit@humanloop.org", "member"),
    ("Chirag Vyas", "chirag.vyas@humanloop.org", "member"),
    ("Madhuri Kale", "madhuri.kale@humanloop.org", "member"),
    ("Ashwin Hegde", "ashwin.hegde@humanloop.org", "member"),
    ("Vandana Luthra", "vandana.luthra@humanloop.org", "member"),
    ("Jayesh Modi", "jayesh.modi@humanloop.org", "member"),
    ("Isha Sengupta", "isha.sengupta@humanloop.org", "member"),
    ("Vishal Raina", "vishal.raina@humanloop.org", "member"),
    ("Namrata Kulshrestha", "namrata.kulshrestha@humanloop.org", "member"),
    ("Hemant Dixit", "hemant.dixit@humanloop.org", "member"),
    ("Rupal Shah", "rupal.shah@humanloop.org", "member"),
    ("Aniket Bhagat", "aniket.bhagat@humanloop.org", "member"),
    ("Sonal Khandelwal", "sonal.khandelwal@humanloop.org", "member"),
    ("Devendra Chouhan", "devendra.chouhan@humanloop.org", "member"),
    ("Payal Raghavan", "payal.raghavan@humanloop.org", "member"),
    ("Sameer Jangid", "sameer.jangid@humanloop.org", "member"),
    ("Chitra Sundaram", "chitra.sundaram@humanloop.org", "member"),
    ("Niranjan Kulkami", "niranjan.kulkami@humanloop.org", "member"),
    ("Varsha Saini", "varsha.saini@humanloop.org", "member"),
    ("Kapil Tandon", "kapil.tandon@humanloop.org", "member"),
    ("Gayatri Nayak", "gayatri.nayak@humanloop.org", "member"),
    ("Lalit Ahluwalia", "lalit.ahluwalia@humanloop.org", "member"),
    ("Meenal Karnik", "meenal.karnik@humanloop.org", "member"),
    ("Partho Ghosh", "partho.ghosh@humanloop.org", "member"),
    ("Shweta Wadhwa", "shweta.wadhwa@humanloop.org", "member"),
    ("Umesh Bajaj", "umesh.bajaj@humanloop.org", "member"),
    ("Archana Kamath", "archana.kamath@humanloop.org", "member"),
    ("Dinesh Ranawat", "dinesh.ranawat@humanloop.org", "member"),
    ("Smriti Chawla", "smriti.chawla@humanloop.org", "member"),
    ("Gopal Kashyap", "gopal.kashyap@humanloop.org", "member"),
    ("Hema Padmanabhan", "hema.padmanabhan@humanloop.org", "member"),
    ("Raghav Khosla", "raghav.khosla@humanloop.org", "member"),
    ("Jhanvi Agnihotri", "jhanvi.agnihotri@humanloop.org", "member"),
]

# Distribution: out of 100 total for full pool
ROLE_POOL = {
    'lead': 10,
    'data_analyst': 5,
    'budget_manager': 5,
    'community_organizer': 5,
    'field_coordinator': 10,
    'member': 65,
}


def get_proportional_count(needed, total=100):
    """Calculate how many of each role to assign proportionally."""
    if needed >= total:
        return dict(ROLE_POOL)

    result = {}
    assigned = 0
    roles = list(ROLE_POOL.items())

    for i, (role, pool_count) in enumerate(roles):
        if i == len(roles) - 1:
            # Last role gets remaining
            result[role] = max(0, needed - assigned)
        else:
            count = max(1, round(pool_count / total * needed))
            result[role] = count
            assigned += count

    return result


class Command(BaseCommand):
    help = 'Seed 100 team members for NSS-Vadodara and assign to pilots proportionally'

    def handle(self, *args, **options):
        # Find the NSS-Vadodara NGO user
        ngo_user = User.objects.filter(
            role='ngo',
            organization__icontains='nss'
        ).first()

        if not ngo_user:
            ngo_user = User.objects.filter(role='ngo').first()

        if not ngo_user:
            self.stderr.write(self.style.ERROR('No NGO user found!'))
            return

        self.stdout.write('Found NGO: %s (%s)' % (ngo_user.name, ngo_user.organization))

        # Step 1: Add all 100 as OrgMembers
        org_name = ngo_user.organization or ngo_user.name
        org_created = 0
        for name, email, role in TEAM_DATA:
            obj, created = OrgMember.objects.update_or_create(
                email=email,
                organization=org_name,
                defaults={
                    'name': name,
                    'job_role': dict(TeamMember.ROLE_CHOICES).get(role, 'Member'),
                    'added_by': ngo_user,
                }
            )
            if created:
                org_created += 1

        self.stdout.write(self.style.SUCCESS(
            '[OK] OrgMembers: %d created, %d updated (org: %s)' % (org_created, 100 - org_created, org_name)
        ))

        # Step 2: For each pilot assigned to this NGO, assign proportionally
        pilots = Pilot.objects.filter(assigned_ngo=ngo_user, status='active')
        if not pilots.exists():
            pilots = Pilot.objects.filter(assigned_ngo=ngo_user)

        self.stdout.write('Found %d pilots for this NGO' % pilots.count())

        # Group team data by role for easy slicing
        by_role = {}
        for name, email, role in TEAM_DATA:
            by_role.setdefault(role, []).append((name, email))

        for pilot in pilots:
            needed = pilot.expected_members or 50
            needed = min(needed, 100)

            self.stdout.write(
                '\nPilot: %s -- needs %d members' % (pilot.title, needed)
            )

            # Calculate proportional distribution
            distribution = get_proportional_count(needed)
            self.stdout.write('   Distribution: %s' % str(distribution))

            # Create or find User accounts for each member, then assign to pilot
            assigned_count = 0
            for role, count in distribution.items():
                members_in_role = by_role.get(role, [])
                for name, email in members_in_role[:count]:
                    # Get or create a user account for this member
                    user, _ = User.objects.get_or_create(
                        email=email,
                        defaults={
                            'name': name,
                            'role': 'ngo',
                            'organization': org_name,
                            'password': 'pbkdf2_sha256$720000$placeholder$not_a_real_password',
                        }
                    )

                    # Assign to pilot's TeamMember
                    tm, created = TeamMember.objects.update_or_create(
                        user=user,
                        pilot=pilot,
                        defaults={'team_role': role}
                    )
                    if created:
                        assigned_count += 1

            self.stdout.write(self.style.SUCCESS(
                '   [OK] Assigned %d new members to "%s"' % (assigned_count, pilot.title)
            ))

        self.stdout.write(self.style.SUCCESS('\nDone! All team members seeded.'))
