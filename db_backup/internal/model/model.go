package model

type PgDumpTaskOutput struct {
	TimestampUnix int64  `json:"timestamp_unix"`
	Timestamp     string `json:"timestamp"`
	WorkflowID    string `json:"workflow_id"`
	BaseDir       string `json:"base_dir"`
	DumpPath      string `json:"dump_path"`
	DumpFileName  string `json:"dump_file_name"`
}

type EncryptTaskOutput struct {
	Timestamp         string `json:"timestamp"`
	WorkflowID        string `json:"workflow_id"`
	BaseDir           string `json:"base_dir"`
	EncryptedPath     string `json:"encrypted_path"`
	EncryptedFileName string `json:"encrypted_file_name"`
	DumpFileName      string `json:"dump_file_name"`
}

type CompressTaskOutput struct {
	Timestamp          string `json:"timestamp"`
	WorkflowID         string `json:"workflow_id"`
	BaseDir            string `json:"base_dir"`
	CompressedPath     string `json:"compressed_path"`
	CompressedFileName string `json:"compressed_file_name"`
}

type UploadTaskOutput struct {
	ObjectKey      string `json:"object_key"`
	ObjectPath     string `json:"object_path"`
	WorkflowID     string `json:"workflow_id"`
	TaskID         string `json:"task_id"`
	DumpFileName   string `json:"dump_file_name"`
	EncryptedName  string `json:"encrypted_file_name"`
	CompressedName string `json:"compressed_file_name"`
	UploadedAtUnix int64  `json:"uploaded_at_unix"`
}

type CleanupTaskOutput struct {
	WorkflowID     string `json:"workflow_id"`
	DeletedBaseDir string `json:"deleted_base_dir"`
	CleanedAtUnix  int64  `json:"cleaned_at_unix"`
}
