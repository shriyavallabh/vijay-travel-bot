import { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, Box, Grid, Typography, CircularProgress } from '@mui/material';
import { Title, useNotify } from 'react-admin';
import PeopleIcon from '@mui/icons-material/People';
import FlightTakeoffIcon from '@mui/icons-material/FlightTakeoff';
import QuestionAnswerIcon from '@mui/icons-material/QuestionAnswer';
import PauseCircleIcon from '@mui/icons-material/PauseCircle';
import TodayIcon from '@mui/icons-material/Today';
import { chatApi } from '../providers/dataProvider';

interface DashboardStats {
  total_users: number;
  active_trips: number;
  pending_queries: number;
  bot_paused_count: number;
  messages_today: number;
  recent_activity: Array<{ date: string; count: number }>;
}

// KPI Card Component
const KpiCard = ({
  title,
  value,
  icon,
  color,
  subtitle,
}: {
  title: string;
  value: number | string;
  icon: React.ReactNode;
  color: string;
  subtitle?: string;
}) => (
  <Card
    sx={{
      minHeight: 140,
      background: `linear-gradient(135deg, ${color} 0%, ${color}dd 100%)`,
      color: 'white',
      position: 'relative',
      overflow: 'hidden',
    }}
  >
    <CardContent>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <Box>
          <Typography variant="h3" component="div" sx={{ fontWeight: 'bold' }}>
            {value}
          </Typography>
          <Typography variant="subtitle1" sx={{ opacity: 0.9 }}>
            {title}
          </Typography>
          {subtitle && (
            <Typography variant="caption" sx={{ opacity: 0.7 }}>
              {subtitle}
            </Typography>
          )}
        </Box>
        <Box
          sx={{
            opacity: 0.3,
            position: 'absolute',
            right: -10,
            top: -10,
            '& svg': { fontSize: 100 },
          }}
        >
          {icon}
        </Box>
      </Box>
    </CardContent>
  </Card>
);

// Welcome Card
const WelcomeCard = () => (
  <Card sx={{ mb: 3, background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)', color: 'white' }}>
    <CardContent>
      <Typography variant="h4" gutterBottom>
        Welcome to Shri Travels Admin
      </Typography>
      <Typography variant="body1">
        Manage your customers, monitor conversations, and take over chats when needed.
      </Typography>
    </CardContent>
  </Card>
);

// Quick Actions Card
const QuickActionsCard = ({ onSyncCustomers }: { onSyncCustomers: () => void }) => (
  <Card>
    <CardHeader title="Quick Actions" />
    <CardContent>
      <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
        <Box
          onClick={onSyncCustomers}
          sx={{
            p: 2,
            border: '1px solid #e0e0e0',
            borderRadius: 2,
            cursor: 'pointer',
            '&:hover': { backgroundColor: '#f5f5f5' },
            textAlign: 'center',
            minWidth: 120,
          }}
        >
          <PeopleIcon color="primary" sx={{ fontSize: 32 }} />
          <Typography variant="body2">Sync Customers</Typography>
        </Box>
        <Box
          component="a"
          href="#/chat"
          sx={{
            p: 2,
            border: '1px solid #e0e0e0',
            borderRadius: 2,
            cursor: 'pointer',
            '&:hover': { backgroundColor: '#f5f5f5' },
            textAlign: 'center',
            minWidth: 120,
            textDecoration: 'none',
            color: 'inherit',
          }}
        >
          <QuestionAnswerIcon color="secondary" sx={{ fontSize: 32 }} />
          <Typography variant="body2">View Chats</Typography>
        </Box>
        <Box
          component="a"
          href="#/users"
          sx={{
            p: 2,
            border: '1px solid #e0e0e0',
            borderRadius: 2,
            cursor: 'pointer',
            '&:hover': { backgroundColor: '#f5f5f5' },
            textAlign: 'center',
            minWidth: 120,
            textDecoration: 'none',
            color: 'inherit',
          }}
        >
          <PeopleIcon color="success" sx={{ fontSize: 32 }} />
          <Typography variant="body2">Customers</Typography>
        </Box>
      </Box>
    </CardContent>
  </Card>
);

export const Dashboard = () => {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const notify = useNotify();

  const fetchStats = async () => {
    try {
      const data = await chatApi.getDashboardStats();
      setStats(data);
    } catch (error) {
      console.error('Failed to fetch stats:', error);
      notify('Failed to load dashboard stats', { type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  const handleSyncCustomers = async () => {
    try {
      const result = await chatApi.syncCustomers();
      notify(result.message, { type: 'success' });
      fetchStats();
    } catch (error) {
      notify('Failed to sync customers', { type: 'error' });
    }
  };

  useEffect(() => {
    fetchStats();
    // Refresh every 30 seconds
    const interval = setInterval(fetchStats, 30000);
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '50vh' }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box sx={{ p: 3 }}>
      <Title title="Dashboard" />

      <WelcomeCard />

      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid item xs={12} sm={6} md={3}>
          <KpiCard
            title="Total Users"
            value={stats?.total_users || 0}
            icon={<PeopleIcon />}
            color="#2196f3"
            subtitle="Registered customers"
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <KpiCard
            title="Active Trips"
            value={stats?.active_trips || 0}
            icon={<FlightTakeoffIcon />}
            color="#4caf50"
            subtitle="Currently traveling"
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <KpiCard
            title="Pending Queries"
            value={stats?.pending_queries || 0}
            icon={<QuestionAnswerIcon />}
            color="#ff9800"
            subtitle="Unread messages"
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <KpiCard
            title="Bot Paused"
            value={stats?.bot_paused_count || 0}
            icon={<PauseCircleIcon />}
            color="#f44336"
            subtitle="Admin takeover"
          />
        </Grid>
      </Grid>

      <Grid container spacing={3}>
        <Grid item xs={12} md={6}>
          <Card>
            <CardHeader title="Today's Activity" />
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                <TodayIcon color="primary" sx={{ fontSize: 48 }} />
                <Box>
                  <Typography variant="h4">{stats?.messages_today || 0}</Typography>
                  <Typography variant="body2" color="text.secondary">
                    Messages exchanged today
                  </Typography>
                </Box>
              </Box>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={6}>
          <QuickActionsCard onSyncCustomers={handleSyncCustomers} />
        </Grid>
      </Grid>
    </Box>
  );
};
