import {
  List,
  Datagrid,
  TextField,
  DateField,
  EditButton,
  Edit,
  SimpleForm,
  TextInput,
  BooleanInput,
  SelectInput,
  useRecordContext,
  useNotify,
  useRefresh,
  TopToolbar,
  FilterButton,
  ExportButton,
  SearchInput,
} from 'react-admin';
import { Box, Chip, IconButton, Tooltip } from '@mui/material';
import ChatIcon from '@mui/icons-material/Chat';
import PauseCircleIcon from '@mui/icons-material/PauseCircle';
import PlayCircleIcon from '@mui/icons-material/PlayCircle';
import { useNavigate } from 'react-router-dom';
import { chatApi } from '../providers/dataProvider';

// Custom Bot Status Toggle Field
const BotStatusField = ({ label: _label }: { label?: string }) => {
  const record = useRecordContext();
  const notify = useNotify();
  const refresh = useRefresh();

  if (!record) return null;

  const handleToggle = async (e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      const result = await chatApi.toggleBotStatus(Number(record.id));
      notify(result.message, { type: 'success' });
      refresh();
    } catch (error) {
      notify('Failed to toggle bot status', { type: 'error' });
    }
  };

  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
      <Chip
        label={record.bot_paused ? 'Paused' : 'Active'}
        color={record.bot_paused ? 'error' : 'success'}
        size="small"
        sx={{ minWidth: 70 }}
      />
      <Tooltip title={record.bot_paused ? 'Resume Bot' : 'Pause Bot (Admin Takeover)'}>
        <IconButton size="small" onClick={handleToggle} color={record.bot_paused ? 'success' : 'warning'}>
          {record.bot_paused ? <PlayCircleIcon /> : <PauseCircleIcon />}
        </IconButton>
      </Tooltip>
    </Box>
  );
};

// Chat Button Field
const ChatButton = () => {
  const record = useRecordContext();
  const navigate = useNavigate();

  if (!record) return null;

  return (
    <Tooltip title="Open Chat">
      <IconButton
        size="small"
        color="primary"
        onClick={(e) => {
          e.stopPropagation();
          navigate(`/chat/${record.id}`);
        }}
      >
        <ChatIcon />
      </IconButton>
    </Tooltip>
  );
};

// Trip Status Field with colored chip
const TripStatusField = ({ label: _label }: { label?: string }) => {
  const record = useRecordContext();
  if (!record) return null;

  const statusColors: Record<string, 'default' | 'primary' | 'success' | 'warning' | 'error'> = {
    upcoming: 'primary',
    active: 'success',
    completed: 'default',
    cancelled: 'error',
  };

  return (
    <Chip
      label={record.trip_status || 'N/A'}
      color={statusColors[record.trip_status] || 'default'}
      size="small"
      sx={{ textTransform: 'capitalize' }}
    />
  );
};

// Filters for the list
const userFilters = [
  <SearchInput source="search" alwaysOn />,
  <SelectInput
    source="trip_status"
    choices={[
      { id: 'upcoming', name: 'Upcoming' },
      { id: 'active', name: 'Active' },
      { id: 'completed', name: 'Completed' },
      { id: 'cancelled', name: 'Cancelled' },
    ]}
  />,
  <BooleanInput source="bot_paused" label="Bot Paused" />,
];

// List Actions
const ListActions = () => (
  <TopToolbar>
    <FilterButton />
    <ExportButton />
  </TopToolbar>
);

// User List Component
export const UserList = () => (
  <List
    filters={userFilters}
    actions={<ListActions />}
    sort={{ field: 'last_message_at', order: 'DESC' }}
    perPage={25}
  >
    <Datagrid rowClick="edit" bulkActionButtons={false}>
      <TextField source="id" label="ID" />
      <TextField source="name" label="Name" emptyText="Unknown" />
      <TextField source="phone" label="Phone" />
      <TripStatusField label="Trip Status" />
      <BotStatusField label="Bot Status" />
      <DateField source="last_message_at" label="Last Message" showTime />
      <TextField source="message_count" label="Messages" />
      <ChatButton />
      <EditButton />
    </Datagrid>
  </List>
);

// User Edit Component
export const UserEdit = () => (
  <Edit>
    <SimpleForm>
      <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', width: '100%' }}>
        <Box sx={{ flex: 1, minWidth: 300 }}>
          <TextInput source="name" fullWidth />
          <TextInput source="phone" fullWidth disabled />
          <TextInput source="email" fullWidth />
        </Box>
        <Box sx={{ flex: 1, minWidth: 300 }}>
          <TextInput source="trip_id" label="Trip ID" fullWidth />
          <SelectInput
            source="trip_status"
            choices={[
              { id: 'upcoming', name: 'Upcoming' },
              { id: 'active', name: 'Active' },
              { id: 'completed', name: 'Completed' },
              { id: 'cancelled', name: 'Cancelled' },
            ]}
            fullWidth
          />
          <BooleanInput source="bot_paused" label="Pause Bot (Admin Takeover)" />
        </Box>
      </Box>
      <TextInput source="notes" multiline rows={4} fullWidth />
    </SimpleForm>
  </Edit>
);
