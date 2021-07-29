import React, { useState, useCallback, useEffect } from 'react';
import {
  Panel,
  Stack,
  PrimaryButton,
  DefaultButton,
  ProgressIndicator,
  Label,
  TextField,
  mergeStyleSets,
  Text,
  Link,
} from '@fluentui/react';
import { assocPath } from 'ramda';
import { useDispatch } from 'react-redux';

import { CreatOwnModelPayload, TrainingProject } from '../../../store/trainingProjectSlice';
import { Part } from '../../../store/partSlice';
import { CreateFormType } from '../type';
import { getSource } from '../utils';

import Tag from '../Tag';

type ModelType = 'custom' | 'own' | 'ovms';

type Props = {
  isOpen: boolean;
  project: TrainingProject;
  parts: Part[];
  modelType: ModelType;
  onDissmiss: () => void;
};

const getClasses = () =>
  mergeStyleSets({
    itemWrapper: {
      marginTop: '25px',
    },
    itemTitle: { fontSize: '13px', lineHeight: '18px', color: '#605E5C' },
    item: { fontSize: '13px', lineHeight: '18px', color: '#000' },
    itemLink: { fontSize: '13px', lineHeight: '18px' },
    tagsWrapper: {
      marginTop: '20px',
    },
  });

const initialForm: CreateFormType = {
  name: '',
  endPoint: '',
  labels: '',
  selectedCustomVisionId: '',
  tags: [],
  category: 'object',
};

const EditPanel: React.FC<Props> = (props) => {
  const { isOpen, project, parts, modelType, onDissmiss } = props;

  const [localTag, setLocalTag] = useState('');
  const [localTags, setLocalTags] = useState<string[]>([]);

  const dispatch = useDispatch();
  const classes = getClasses();

  useEffect(() => {
    setLocalTags([...parts].map((part) => part.name));
  }, [parts]);

  const onTagAdd = useCallback(
    (event: React.KeyboardEvent<HTMLInputElement>) => {
      if (event.key === 'Enter' && localTag !== '') {
        setLocalTags((prev) => [...prev, localTag]);
        setLocalTag('');
      }
    },
    [localTag],
  );

  const onRemoveTag = useCallback(
    (idx: number) => {
      const newTags = [...localTags];
      newTags.splice(idx, 1);

      setLocalTags(newTags);
    },
    [localTags],
  );

  return (
    <Panel
      isOpen={isOpen}
      onDismiss={onDissmiss}
      hasCloseButton
      headerText="Edit Model"
      onRenderFooterContent={() => (
        <Stack tokens={{ childrenGap: 10 }} horizontal>
          {/* {selectedType === 'custom' && (
            <PrimaryButton onClick={onLoadModel} disabled={isLoading} text="Load" />
          )}
          {selectedType === 'own' && (
            <PrimaryButton onClick={onCreateModel} disabled={isLoading} text="Add" />
          )} */}
          <PrimaryButton onClick={() => {}} text="Save" />
          <DefaultButton onClick={onDissmiss}>Cancel</DefaultButton>
        </Stack>
      )}
      isFooterAtBottom={true}
    >
      {/* <ProgressIndicator progressHidden={!isLoading} /> */}
      <Stack styles={{ root: classes.itemWrapper }} tokens={{ childrenGap: 16 }}>
        <Stack>
          <Label styles={{ root: classes.itemTitle }}>Source</Label>
          <Text styles={{ root: classes.item }}>{getSource(modelType)}</Text>
        </Stack>
        <Stack>
          <Label styles={{ root: classes.itemTitle }}>Trainable</Label>
          <Text styles={{ root: classes.item }}>{modelType === 'custom' ? 'True' : 'False'}</Text>
        </Stack>
        {project.customVisionId && (
          <Stack>
            <Label styles={{ root: classes.itemTitle }}>Name</Label>
            <Link styles={{ root: classes.itemLink }}>{project.name}</Link>
          </Stack>
        )}
        {modelType !== 'custom' && (
          <Stack>
            <Label styles={{ root: classes.itemTitle }}>Object / Tags</Label>
            <Stack horizontal wrap>
              {parts.map((part, id) => (
                <Tag id={id} text={part.name} />
              ))}
            </Stack>
          </Stack>
        )}
      </Stack>
      <Stack styles={{ root: classes.tagsWrapper }} tokens={{ childrenGap: '10px' }}>
        <TextField
          label="Objects/Tags"
          onChange={(_, newValue) => setLocalTag(newValue)}
          onKeyPress={onTagAdd}
        />
        <Stack horizontal tokens={{ childrenGap: '8px' }} wrap>
          {localTags.map((part, id) => (
            <Tag key={id} id={id} text={part} isDelete onDelete={onRemoveTag} />
          ))}
        </Stack>
      </Stack>
    </Panel>
  );
};

export default EditPanel;
