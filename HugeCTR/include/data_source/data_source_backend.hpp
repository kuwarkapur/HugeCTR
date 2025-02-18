/*
 * Copyright (c) 2021, NVIDIA CORPORATION.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

#pragma once

#include <string>
#include <vector>

namespace HugeCTR {
class DataSourceBackend {
 public:
  DataSourceBackend() = default;

  DataSourceBackend(const DataSourceBackend&) = delete;

  virtual ~DataSourceBackend() = default;

  DataSourceBackend& operator=(const DataSourceBackend&) = delete;

  /**
   * @brief Get the file size of target file from the file system
   *
   * @return the file size
   */
  virtual size_t getFileSize(const std::string& path) const = 0;

  /**
   * @brief Write file from butter to the specified path in the file system
   *
   * @return the number of bytes successfully written
   */
  virtual int write(const std::string& writepath, const void* data, size_t dataSize,
                    bool overwrite) = 0;

  /**
   * @brief Read file from the file system to the buffer
   *
   * @return the number of bytes successfully read
   */
  virtual int read(const std::string& readpath, const void* buffer, size_t data_size,
                   size_t offset) = 0;

  /**
   * @brief Copy a specific file from the file system to the local SSD.
   *
   * @return the number of bytes successfully copy
   */
  virtual int copyToLocal(const std::string& hdfs_path, const std::string& local_path) = 0;
};
}  // namespace HugeCTR