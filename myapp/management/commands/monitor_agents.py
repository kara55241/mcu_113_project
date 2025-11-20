import time
import sqlite3
import pickle
import json
from datetime import datetime, timedelta
from collections import defaultdict
from django.core.management.base import BaseCommand
from myproject.views import ChatHistory

class DatabaseMonitor:
    """Monitor SQLite checkpoint database changes"""
    
    def __init__(self, db_path="./agent_checkpoint_new.sqlite"):
        self.db_path = db_path
        
    def connect(self):
        """Connect to checkpoint database"""
        try:
            return sqlite3.connect(self.db_path)
        except Exception as e:
            print(f"Database connection failed: {str(e)}")
            return None
    
    def get_recent_checkpoints(self, limit=100):
        """Get recent checkpoint data"""
        conn = self.connect()
        if not conn:
            return []
        
        try:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT thread_id, checkpoint_id, parent_checkpoint_id, 
                          checkpoint, metadata 
                   FROM checkpoints 
                   ORDER BY checkpoint_id DESC LIMIT ?""", (limit,)
            )
            results = cursor.fetchall()
            conn.close()
            return results
        except Exception as e:
            print(f"Query checkpoints failed: {str(e)}")
            conn.close()
            return []
    
    def get_active_threads(self):
        """Get active thread IDs"""
        conn = self.connect()
        if not conn:
            return []
        
        try:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT DISTINCT thread_id 
                   FROM checkpoints 
                   ORDER BY checkpoint_id DESC LIMIT 50"""
            )
            results = [row[0] for row in cursor.fetchall()]
            conn.close()
            return results
        except Exception as e:
            print(f"Get active threads failed: {str(e)}")
            conn.close()
            return []

class AgentStateAnalyzer:
    """Analyze agent state and tool calls"""

    def __init__(self):
        # 新並行架構的節點/工具模式
        self.agent_patterns = {
            # 新架構 supervisor 節點
            'supervisor_task_analysis': 'task_analysis',
            'supervisor_analysis': 'task_analysis',  # 備用別名
            'supervisor_routing': 'fast_path',
            'supervisor_fast_path': 'fast_path',  # 舊名稱備用
            # Agent 節點
            'chronic_agent': 'chronic_search',
            'cardiovascular_agent': 'cardiovascular_search',
            'fact_check_agent': ['google_fact_check_tool', 'cofacts_check_tool', 'net_search'],
            # 整合節點（新並行架構）
            'integration': 'agent_responses',
            'integration_node': 'agent_responses',  # 備用別名
            # 舊架構（保留兼容）
            'supervisor': 'transfer_to_',
            'supervisor_decomposition': 'subtasks'
        }
        
    def analyze_checkpoint(self, checkpoint_blob):
        """Analyze checkpoint data to identify agents and tool calls"""
        analysis = {
            'current_agent': 'unknown',
            'tools_called': [],
            'routing_decision': None,
            'status': 'processing',
            'error': None
        }
        
        if not checkpoint_blob:
            return analysis
        
        try:
            # Try to deserialize checkpoint data
            data = pickle.loads(checkpoint_blob)
            
            if isinstance(data, dict):
                # Look for messages in checkpoint data
                messages = data.get('channel_values', {}).get('messages', [])
                
                # Analyze recent messages
                for message in messages[-10:]:
                    if hasattr(message, 'content'):
                        content = str(message.content)
                    elif isinstance(message, dict) and 'content' in message:
                        content = str(message['content'])
                    else:
                        continue
                        
                    # Detect routing decisions
                    if 'transfer_to_' in content:
                        if 'chronic_agent' in content:
                            analysis['routing_decision'] = 'chronic_agent'
                        elif 'cardiovascular_agent' in content:
                            analysis['routing_decision'] = 'cardiovascular_agent'
                        elif 'fact_check_agent' in content:
                            analysis['routing_decision'] = 'fact_check_agent'
                    
                    # Detect tool calls
                    for agent, tool_pattern in self.agent_patterns.items():
                        if tool_pattern in content:
                            analysis['current_agent'] = agent
                            if tool_pattern not in analysis['tools_called']:
                                analysis['tools_called'].append(tool_pattern)
                
                # Check node status
                if 'next' in data:
                    next_nodes = data.get('next', [])
                    if next_nodes:
                        analysis['status'] = f'waiting_for_{next_nodes[0]}'
                        
        except Exception as e:
            analysis['error'] = f"Analysis error: {str(e)}"
        
        return analysis

class Command(BaseCommand):
    help = 'Monitor multi-agent system real-time status and sessions'
    
    def __init__(self):
        super().__init__()
        self.db_monitor = DatabaseMonitor()
        self.state_analyzer = AgentStateAnalyzer()
        self.running = False
        
    def add_arguments(self, parser):
        parser.add_argument(
            '--live',
            action='store_true',
            help='Enable real-time monitoring mode'
        )
        parser.add_argument(
            '--session',
            type=str,
            help='Monitor specific session ID'
        )
        parser.add_argument(
            '--status',
            action='store_true',
            help='Show system status overview'
        )
        parser.add_argument(
            '--history',
            action='store_true',
            help='Show historical analysis'
        )
        parser.add_argument(
            '--hours',
            type=int,
            default=1,
            help='Hours for historical analysis (default: 1)'
        )
        parser.add_argument(
            '--refresh',
            type=int,
            default=2,
            help='Refresh interval in seconds (default: 2)'
        )
    
    def handle(self, *args, **options):
        try:
            if options['live']:
                self.live_monitor(options)
            elif options['session']:
                self.monitor_session(options['session'])
            elif options['status']:
                self.show_status()
            elif options['history']:
                self.show_history(options['hours'])
            else:
                self.show_help()
                
        except KeyboardInterrupt:
            self.stdout.write("\nMonitoring stopped")
        except Exception as e:
            self.stdout.write(f"Error during monitoring: {str(e)}")
    
    def live_monitor(self, options):
        """Real-time monitoring mode"""
        self.running = True
        refresh_interval = options.get('refresh', 2)
        
        self.stdout.write("="*50)
        self.stdout.write("Multi-Agent System Real-time Monitor")
        self.stdout.write("="*50)
        self.stdout.write(f"Refresh interval: {refresh_interval}s | Press Ctrl+C to exit\n")
        
        last_checkpoint_count = 0
        
        while self.running:
            try:
                # Get latest checkpoint data
                checkpoints = self.db_monitor.get_recent_checkpoints()
                current_checkpoint_count = len(checkpoints)
                
                # Detect new activity
                if current_checkpoint_count > last_checkpoint_count:
                    new_checkpoints = checkpoints[:current_checkpoint_count - last_checkpoint_count]
                    for checkpoint in new_checkpoints:
                        self.process_checkpoint_update(checkpoint)
                    last_checkpoint_count = current_checkpoint_count
                
                # Display current status
                active_threads = self.db_monitor.get_active_threads()
                status_line = f"Status: Active threads: {len(active_threads)} | Total checkpoints: {len(checkpoints)}"
                self.stdout.write(f"\r{status_line}", ending="")
                self.stdout.flush()
                
                time.sleep(refresh_interval)
                
            except KeyboardInterrupt:
                self.running = False
                break
            except Exception as e:
                self.stdout.write(f"Monitor loop error: {str(e)}")
                time.sleep(refresh_interval)
    
    def process_checkpoint_update(self, checkpoint):
        """Process checkpoint update"""
        thread_id, checkpoint_id, parent_id, checkpoint_blob, metadata = checkpoint
        
        timestamp = datetime.now().strftime("%H:%M:%S")
        session_id = thread_id[:8] if thread_id else "unknown"
        
        # Analyze checkpoint data
        analysis = self.state_analyzer.analyze_checkpoint(checkpoint_blob)
        
        # Display updates
        if analysis.get('routing_decision'):
            self.stdout.write(f"[{timestamp}] Session {session_id}: Routing -> {analysis['routing_decision']}")
        
        for tool in analysis.get('tools_called', []):
            self.stdout.write(f"[{timestamp}] Session {session_id}: Tool call -> {tool}")
        
        if analysis.get('current_agent') and analysis['current_agent'] != 'unknown':
            self.stdout.write(f"[{timestamp}] Session {session_id}: Current agent -> {analysis['current_agent']}")
    
    def monitor_session(self, session_id):
        """Monitor specific session"""
        self.stdout.write(f"Monitoring session: {session_id}\n")
        
        # Find related thread IDs
        active_threads = self.db_monitor.get_active_threads()
        related_threads = [tid for tid in active_threads if session_id in tid]
        
        if not related_threads:
            self.stdout.write("No related active threads found")
            return
        
        self.stdout.write(f"Found {len(related_threads)} related threads:")
        for thread_id in related_threads:
            self.stdout.write(f"  - {thread_id}")
        
        # Get session history
        try:
            chat_history = ChatHistory.get_chat_history(session_id)
            if chat_history:
                self.stdout.write(f"\nSession history:")
                for msg in chat_history[-5:]:  # Show last 5 messages
                    timestamp = datetime.fromtimestamp(msg['timestamp']).strftime("%H:%M:%S")
                    sender = msg['sender']
                    content = msg['content'][:100] + "..." if len(msg['content']) > 100 else msg['content']
                    self.stdout.write(f"[{timestamp}] {sender}: {content}")
        except Exception as e:
            self.stdout.write(f"Failed to get session history: {str(e)}")
    
    def show_status(self):
        """Show system status overview"""
        self.stdout.write("="*50)
        self.stdout.write("Multi-Agent System Status Overview")
        self.stdout.write("="*50)
        
        # Checkpoint database status
        checkpoints = self.db_monitor.get_recent_checkpoints()
        active_threads = self.db_monitor.get_active_threads()
        
        self.stdout.write("Checkpoint Database:")
        self.stdout.write(f"  Recent checkpoints: {len(checkpoints)}")
        self.stdout.write(f"  Active threads: {len(active_threads)}")
        
        # Django sessions status
        try:
            django_sessions = ChatHistory.get_all_chats()
            self.stdout.write(f"\nDjango Sessions:")
            self.stdout.write(f"  Total sessions: {len(django_sessions)}")
            
            if django_sessions:
                self.stdout.write(f"\nRecent sessions:")
                for session in django_sessions[:5]:
                    timestamp = datetime.fromtimestamp(session.get('timestamp', time.time())).strftime("%Y-%m-%d %H:%M:%S")
                    title = session.get('title', 'Unknown title')
                    session_id = session.get('id', 'unknown')[:8]
                    self.stdout.write(f"  [{timestamp}] {session_id}: {title}")
        except Exception as e:
            self.stdout.write(f"Failed to get Django sessions: {str(e)}")
        
        # System health check
        self.stdout.write(f"\nSystem Health:")
        
        # Check database connection
        db_conn = self.db_monitor.connect()
        if db_conn:
            db_conn.close()
            self.stdout.write(f"  Database connection: OK")
        else:
            self.stdout.write(f"  Database connection: FAILED")
        
        # Check multi-agent module
        try:
            from graph_rag_agent.multi_agent import workflow, new_workflow
            self.stdout.write(f"  Multi-agent module: OK")
            self.stdout.write(f"  Current workflow: new_workflow (任務指派型)")
        except ImportError as e:
            self.stdout.write(f"  Multi-agent module: FAILED - {str(e)}")
    
    def show_history(self, hours=1):
        """Show historical analysis"""
        self.stdout.write(f"Historical Analysis (past {hours} hour(s))\n")
        
        # Get historical checkpoints
        checkpoints = self.db_monitor.get_recent_checkpoints(200)  # Get more for analysis
        
        if not checkpoints:
            self.stdout.write("No historical data found")
            return
        
        # Analyze historical data
        thread_activity = defaultdict(int)
        agent_usage = defaultdict(int)
        tool_calls = defaultdict(int)
        
        for checkpoint in checkpoints:
            thread_id = checkpoint[0]
            analysis = self.state_analyzer.analyze_checkpoint(checkpoint[3])
            
            thread_activity[thread_id] += 1
            
            if analysis.get('current_agent') and analysis['current_agent'] != 'unknown':
                agent_usage[analysis['current_agent']] += 1
            
            for tool in analysis.get('tools_called', []):
                tool_calls[tool] += 1
        
        # Display analysis results
        self.stdout.write("Thread Activity (top 5):")
        for thread_id, count in sorted(thread_activity.items(), key=lambda x: x[1], reverse=True)[:5]:
            short_id = thread_id[:8] if thread_id else "unknown"
            self.stdout.write(f"  {short_id}: {count} activities")
        
        self.stdout.write(f"\nAgent Usage Statistics:")
        for agent, count in sorted(agent_usage.items(), key=lambda x: x[1], reverse=True):
            self.stdout.write(f"  {agent}: {count} calls")
        
        self.stdout.write(f"\nTool Call Statistics:")
        for tool, count in sorted(tool_calls.items(), key=lambda x: x[1], reverse=True):
            self.stdout.write(f"  {tool}: {count} calls")
        
        self.stdout.write(f"\nSummary:")
        self.stdout.write(f"  Total checkpoints: {len(checkpoints)}")
        self.stdout.write(f"  Active threads: {len(thread_activity)}")
        self.stdout.write(f"  Agent calls: {sum(agent_usage.values())}")
        self.stdout.write(f"  Tool calls: {sum(tool_calls.values())}")
    
    def show_help(self):
        """Show help information"""
        self.stdout.write("Multi-Agent System Monitor Commands\n")
        self.stdout.write("Usage:")
        self.stdout.write("  python manage.py monitor_agents --live")
        self.stdout.write("    Enable real-time monitoring mode")
        self.stdout.write("  python manage.py monitor_agents --session <session_id>")
        self.stdout.write("    Monitor specific session")
        self.stdout.write("  python manage.py monitor_agents --status")
        self.stdout.write("    Show system status overview")
        self.stdout.write("  python manage.py monitor_agents --history --hours 24")
        self.stdout.write("    Show historical analysis")
        self.stdout.write(f"\nOther parameters:")
        self.stdout.write("  --refresh <seconds>    Set refresh interval (default: 2s)")
        self.stdout.write("  --hours <hours>        Historical analysis time range (default: 1h)")